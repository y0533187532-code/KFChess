"""Capacity and load smoke tests for the production server stack."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import pytest
import websockets

from kongfu_chess.client import WebSocketClientTransport
from kongfu_chess.protocol import EnvelopePolicy, MessageType
from kongfu_chess.server.server_application import (
    build_server_stack,
    shutdown_stack,
)


CONFIG_PATH = Path(__file__).parents[2] / "config" / "server.json"
pytestmark = pytest.mark.load


def make_capacity_config(
    tmp_path,
    *,
    websocket_connections: int,
    active_games: int,
    matchmaking_users: int,
    spectators_per_room: int,
    backup_interval_hours: int = 24,
):
    document = copy.deepcopy(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    document["database"]["path"] = str(tmp_path / "capacity.sqlite3")
    document["database"]["backup_directory"] = str(tmp_path / "backups")
    document["logging"]["server_path"] = str(tmp_path / "server.jsonl")
    document["logging"]["client_path"] = str(tmp_path / "client.jsonl")
    document["security"]["scrypt_n"] = 1024
    document["capacity"]["websocket_connections"] = websocket_connections
    document["capacity"]["active_games"] = active_games
    document["capacity"]["matchmaking_users"] = matchmaking_users
    document["capacity"]["spectators_per_room"] = spectators_per_room
    document["database"]["backup_interval_hours"] = backup_interval_hours
    from kongfu_chess.infrastructure.configuration import ConfigProvider

    return ConfigProvider.from_mapping(document, base_directory=tmp_path)


def envelope(message_type, payload, request_id, *, policy):
    from kongfu_chess.protocol import MessageEnvelope

    return MessageEnvelope.from_mapping(
        {
            "protocol_version": policy.protocol_version,
            "type": message_type,
            "request_id": request_id,
            "timestamp_ms": 1000,
            "payload": payload,
        },
        policy,
    )


def request(transport, message_type, payload, request_id, *, policy):
    return transport.request(
        envelope(message_type, payload, request_id, policy=policy)
    )


def register_and_login(transport, username, request_id, *, policy, stack=None, rating=None):
    request(
        transport,
        MessageType.REGISTER_REQUEST.value,
        {
            "username": username,
            "password": "secret7",
            "email": f"{username}@example.test",
            "phone": "0501234567",
        },
        request_id,
        policy=policy,
    )
    logged_in = request(
        transport,
        MessageType.LOGIN_REQUEST.value,
        {"username": username, "password": "secret7"},
        f"{request_id}-login",
        policy=policy,
    )
    if stack is not None and rating is not None:
        user_id = logged_in.payload["user_id"]
        with stack.database.transaction() as connection:
            connection.execute(
                "UPDATE users SET rating = ? WHERE id = ?",
                (rating, user_id),
            )
    return logged_in.payload["auth_token"]


def test_websocket_connection_limit(tmp_path):
    config = make_capacity_config(
        tmp_path,
        websocket_connections=3,
        active_games=10,
        matchmaking_users=20,
        spectators_per_room=3,
    )
    stack = build_server_stack(config)

    async def scenario():
        server = await stack.gateway.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        sockets = []
        try:
            for _ in range(3):
                sockets.append(await websockets.connect(uri, open_timeout=2))
            assert await stack.connections.count() == 3
            fourth = await websockets.connect(uri, open_timeout=2)
            await asyncio.sleep(0.05)
            assert await stack.connections.count() == 3
            assert fourth.close_code == 1013
        finally:
            for socket in sockets:
                await socket.close()
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_active_games_limit(tmp_path):
    config = make_capacity_config(
        tmp_path,
        websocket_connections=50,
        active_games=2,
        matchmaking_users=20,
        spectators_per_room=3,
    )
    stack = build_server_stack(config)
    policy = EnvelopePolicy(
        config.network.protocol_version,
        config.network.max_message_bytes,
        config.network.request_id_max_length,
        config.network.message_type_max_length,
    )

    async def scenario():
        server = await stack.gateway.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        try:
            def run_matchmaking():
                transport = WebSocketClientTransport(uri, policy)
                try:
                    white = register_and_login(
                        transport, "white1", "white1", policy=policy
                    )
                    black = register_and_login(
                        transport, "black1", "black1", policy=policy
                    )
                    request(
                        transport,
                        MessageType.PLAY_QUEUE_JOIN.value,
                        {"auth_token": white},
                        "join-white",
                        policy=policy,
                    )
                    matched = request(
                        transport,
                        MessageType.PLAY_QUEUE_JOIN.value,
                        {"auth_token": black},
                        "join-black",
                        policy=policy,
                    )
                    assert matched.payload["state"] == "match_found"

                    white2 = register_and_login(
                        transport, "white2", "white2", policy=policy
                    )
                    black2 = register_and_login(
                        transport, "black2", "black2", policy=policy
                    )
                    request(
                        transport,
                        MessageType.PLAY_QUEUE_JOIN.value,
                        {"auth_token": white2},
                        "join-white2",
                        policy=policy,
                    )
                    matched2 = request(
                        transport,
                        MessageType.PLAY_QUEUE_JOIN.value,
                        {"auth_token": black2},
                        "join-black2",
                        policy=policy,
                    )
                    assert matched2.payload["state"] == "match_found"

                    white3 = register_and_login(
                        transport, "white3", "white3", policy=policy
                    )
                    black3 = register_and_login(
                        transport, "black3", "black3", policy=policy
                    )
                    request(
                        transport,
                        MessageType.PLAY_QUEUE_JOIN.value,
                        {"auth_token": white3},
                        "join-white3",
                        policy=policy,
                    )
                    rejected = request(
                        transport,
                        MessageType.PLAY_QUEUE_JOIN.value,
                        {"auth_token": black3},
                        "join-black3",
                        policy=policy,
                    )
                    assert rejected.payload["accepted"] is False
                    assert rejected.payload["code"] == "active_games_full"
                finally:
                    transport.close()

            await asyncio.to_thread(run_matchmaking)
        finally:
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_matchmaking_queue_capacity(tmp_path):
    config = make_capacity_config(
        tmp_path,
        websocket_connections=50,
        active_games=50,
        matchmaking_users=3,
        spectators_per_room=3,
    )
    stack = build_server_stack(config)
    policy = EnvelopePolicy(
        config.network.protocol_version,
        config.network.max_message_bytes,
        config.network.request_id_max_length,
        config.network.message_type_max_length,
    )

    async def scenario():
        server = await stack.gateway.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        try:
            def run_queue():
                transport = WebSocketClientTransport(uri, policy)
                try:
                    tokens = [
                        register_and_login(
                            transport,
                            f"queued{index}",
                            f"queued{index}",
                            policy=policy,
                            stack=stack,
                            rating=1000 + index * 200,
                        )
                        for index in range(3)
                    ]
                    for index, token in enumerate(tokens):
                        joined = request(
                            transport,
                            MessageType.PLAY_QUEUE_JOIN.value,
                            {"auth_token": token},
                            f"join-{index}",
                            policy=policy,
                        )
                        assert joined.payload["accepted"] is True
                    overflow = register_and_login(
                        transport,
                        "overflow",
                        "overflow",
                        policy=policy,
                        stack=stack,
                        rating=1800,
                    )
                    rejected = request(
                        transport,
                        MessageType.PLAY_QUEUE_JOIN.value,
                        {"auth_token": overflow},
                        "join-overflow",
                        policy=policy,
                    )
                    assert rejected.payload["accepted"] is False
                    assert rejected.payload["code"] == "matchmaking_queue_full"
                finally:
                    transport.close()

            await asyncio.to_thread(run_queue)
        finally:
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_room_spectator_snapshot_broadcast(tmp_path):
    config = make_capacity_config(
        tmp_path,
        websocket_connections=50,
        active_games=50,
        matchmaking_users=20,
        spectators_per_room=3,
    )
    stack = build_server_stack(config)
    policy = EnvelopePolicy(
        config.network.protocol_version,
        config.network.max_message_bytes,
        config.network.request_id_max_length,
        config.network.message_type_max_length,
    )

    async def scenario():
        server = await stack.gateway.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        try:
            def run_room():
                creator_transport = WebSocketClientTransport(uri, policy)
                joiner_transport = WebSocketClientTransport(uri, policy)
                spectator_transport = WebSocketClientTransport(uri, policy)
                try:
                    creator = register_and_login(
                        creator_transport, "creator", "creator", policy=policy
                    )
                    created = request(
                        creator_transport,
                        MessageType.ROOM_CREATE.value,
                        {"auth_token": creator},
                        "room-create",
                        policy=policy,
                    )
                    room_code = created.payload["code"]

                    joiner = register_and_login(
                        joiner_transport, "joiner", "joiner", policy=policy
                    )
                    joined = request(
                        joiner_transport,
                        MessageType.ROOM_JOIN.value,
                        {"auth_token": joiner, "code": room_code},
                        "room-join",
                        policy=policy,
                    )
                    assert joined.payload["gameplay_started"] is True

                    spectator = register_and_login(
                        spectator_transport, "spectator", "spectator", policy=policy
                    )
                    spectating = request(
                        spectator_transport,
                        MessageType.ROOM_JOIN.value,
                        {"auth_token": spectator, "code": room_code},
                        "room-spectate",
                        policy=policy,
                    )
                    assert spectating.payload["role"] == "SPECTATOR"
                    assert spectating.payload["snapshot"] is not None
                    assert spectating.payload["snapshot"]["pieces"]
                finally:
                    creator_transport.close()
                    joiner_transport.close()
                    spectator_transport.close()

            await asyncio.to_thread(run_room)
        finally:
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_database_backup_writes_file(tmp_path):
    config = make_capacity_config(
        tmp_path,
        websocket_connections=10,
        active_games=10,
        matchmaking_users=10,
        spectators_per_room=3,
    )
    stack = build_server_stack(config)
    backup_path = stack.database.backup_to(
        config.database.backup_directory,
        timestamp_ms=1000,
    )
    from kongfu_chess.server.event_logger import ServerEventLogger

    ServerEventLogger(stack.logger).event("backup_completed", path=str(backup_path))
    assert backup_path.exists()
    log_lines = Path(config.logging.server_path).read_text(encoding="utf-8").splitlines()
    assert any('"event":"backup_completed"' in line for line in log_lines)
