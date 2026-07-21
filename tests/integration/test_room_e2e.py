import asyncio
import copy
import json
from pathlib import Path

from kongfu_chess.client import WebSocketClientTransport
from kongfu_chess.infrastructure.configuration import ConfigProvider
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope, MessageType
from kongfu_chess.server.server_application import (
    build_server_stack,
    shutdown_stack,
)


CONFIG_PATH = Path(__file__).parents[2] / "config" / "server.json"


def make_test_config(tmp_path):
    document = copy.deepcopy(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    document["database"]["path"] = str(tmp_path / "room-e2e.sqlite3")
    document["database"]["backup_directory"] = str(tmp_path / "backups")
    document["logging"]["server_path"] = str(tmp_path / "server.jsonl")
    document["logging"]["client_path"] = str(tmp_path / "client.jsonl")
    document["security"]["scrypt_n"] = 1024
    return ConfigProvider.from_mapping(document, base_directory=tmp_path)


def envelope(message_type, payload, request_id, *, policy):
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


def register_and_login(transport, username, request_id, *, policy):
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
    return logged_in.payload["auth_token"]


def started_room(uri, policy, stack):
    creator = WebSocketClientTransport(uri, policy)
    opponent = WebSocketClientTransport(uri, policy)
    creator_auth = register_and_login(creator, "Creator", "creator-register", policy=policy)
    opponent_auth = register_and_login(
        opponent, "Opponent", "opponent-register", policy=policy
    )
    created = request(
        creator,
        MessageType.ROOM_CREATE.value,
        {"auth_token": creator_auth},
        "room-create",
        policy=policy,
    )
    assert created.payload["accepted"] is True, created.payload
    room_code = created.payload["code"]
    joined = request(
        opponent,
        MessageType.ROOM_JOIN.value,
        {"auth_token": opponent_auth, "code": room_code},
        "room-join",
        policy=policy,
    )
    assert joined.payload["accepted"] is True, joined.payload
    assert joined.payload["gameplay_started"] is True
    game_id = joined.payload["game_id"]
    assert stack.registry.get(game_id) is not None
    return {
        "creator": creator,
        "opponent": opponent,
        "creator_auth": creator_auth,
        "opponent_auth": opponent_auth,
        "creator_room": created.payload,
        "opponent_room": joined.payload,
        "room_code": room_code,
        "game_id": game_id,
    }


def test_room_auto_start_and_resync(tmp_path):
    config = make_test_config(tmp_path)
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
        room = None
        try:
            room = await asyncio.to_thread(started_room, uri, policy, stack)
            assert stack.registry.get(room["game_id"]) is not None

            resync = await asyncio.to_thread(
                request,
                room["creator"],
                MessageType.RESYNC_REQUEST.value,
                {
                    "auth_token": room["creator_auth"],
                    "game_token": room["creator_room"]["game_token"],
                    "game_id": room["game_id"],
                },
                "creator-resync",
                policy=policy,
            )
            assert resync.type == MessageType.SNAPSHOT.value
            assert "pieces" in resync.payload
        finally:
            if room is not None:
                room["creator"].close()
                room["opponent"].close()
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_spectator_receives_snapshot_and_cannot_move(tmp_path):
    config = make_test_config(tmp_path)
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
        room = None
        spectator = None
        try:
            room = await asyncio.to_thread(started_room, uri, policy, stack)
            spectator = WebSocketClientTransport(uri, policy)
            spectator_auth = await asyncio.to_thread(
                register_and_login,
                spectator,
                "Viewer",
                "viewer-register",
                policy=policy,
            )
            joined = await asyncio.to_thread(
                request,
                spectator,
                MessageType.ROOM_JOIN.value,
                {
                    "auth_token": spectator_auth,
                    "code": room["room_code"],
                },
                "spectator-join",
                policy=policy,
            )
            assert joined.payload["accepted"] is True, joined.payload
            assert joined.payload["role"] == "SPECTATOR"
            assert joined.payload["snapshot"] is not None
            assert "pieces" in joined.payload["snapshot"]

            pawn = next(
                piece
                for piece in joined.payload["snapshot"]["pieces"]
                if piece["row"] == 6 and piece["col"] == 0 and piece["token"] == "wP"
            )
            rejected = await asyncio.to_thread(
                request,
                spectator,
                MessageType.MOVE_REQUEST.value,
                {
                    "auth_token": spectator_auth,
                    "game_token": joined.payload["game_token"],
                    "game_id": room["game_id"],
                    "piece_id": pawn["piece_id"],
                    "expected_from": {"row": 6, "col": 0},
                    "target": {"row": 4, "col": 0},
                },
                "spectator-move",
                policy=policy,
            )
            assert rejected.payload["accepted"] is False
            assert rejected.payload["code"] == "forbidden"
        finally:
            if room is not None:
                room["creator"].close()
                room["opponent"].close()
            if spectator is not None:
                spectator.close()
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_creator_leave_before_start_closes_room(tmp_path):
    config = make_test_config(tmp_path)
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
        creator = None
        opponent = None
        try:
            creator = WebSocketClientTransport(uri, policy)
            opponent = WebSocketClientTransport(uri, policy)
            creator_auth = await asyncio.to_thread(
                register_and_login,
                creator,
                "Host",
                "host-register",
                policy=policy,
            )
            opponent_auth = await asyncio.to_thread(
                register_and_login,
                opponent,
                "Guest",
                "guest-register",
                policy=policy,
            )
            created = await asyncio.to_thread(
                request,
                creator,
                MessageType.ROOM_CREATE.value,
                {"auth_token": creator_auth},
                "create-only",
                policy=policy,
            )
            room_code = created.payload["code"]
            left = await asyncio.to_thread(
                request,
                creator,
                MessageType.ROOM_LEAVE.value,
                {"auth_token": creator_auth, "code": room_code},
                "creator-leave",
                policy=policy,
            )
            assert left.payload["accepted"] is True, left.payload
            assert left.payload["status"] == "CLOSED"

            closed = await asyncio.to_thread(
                request,
                opponent,
                MessageType.ROOM_JOIN.value,
                {"auth_token": opponent_auth, "code": room_code},
                "join-closed",
                policy=policy,
            )
            assert closed.payload["accepted"] is False
            assert closed.payload["code"] == "room_closed"
        finally:
            if creator is not None:
                creator.close()
            if opponent is not None:
                opponent.close()
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_active_play_blocks_room_join(tmp_path):
    config = make_test_config(tmp_path)
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
        white = None
        black = None
        try:
            white = WebSocketClientTransport(uri, policy)
            black = WebSocketClientTransport(uri, policy)
            white_auth = await asyncio.to_thread(
                register_and_login, white, "PlayA", "play-a", policy=policy
            )
            black_auth = await asyncio.to_thread(
                register_and_login, black, "PlayB", "play-b", policy=policy
            )
            await asyncio.to_thread(
                request,
                white,
                MessageType.PLAY_QUEUE_JOIN.value,
                {"auth_token": white_auth},
                "queue-a",
                policy=policy,
            )
            matched = await asyncio.to_thread(
                request,
                black,
                MessageType.PLAY_QUEUE_JOIN.value,
                {"auth_token": black_auth},
                "queue-b",
                policy=policy,
            )
            assert matched.type == MessageType.PLAY_MATCH_FOUND.value

            host = await asyncio.to_thread(
                request,
                white,
                MessageType.ROOM_CREATE.value,
                {"auth_token": white_auth},
                "blocked-room",
                policy=policy,
            )
            assert host.payload["accepted"] is False
            assert host.payload["code"] == "already_in_game"
        finally:
            if white is not None:
                white.close()
            if black is not None:
                black.close()
            await shutdown_stack(stack)

    asyncio.run(scenario())
