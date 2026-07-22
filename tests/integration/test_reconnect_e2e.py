import asyncio
import copy
import json
import time
from pathlib import Path
from queue import Empty

from kongfu_chess.client import WebSocketClientTransport
from kongfu_chess.infrastructure.configuration import ConfigProvider
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope, MessageType
from kongfu_chess.server import (
    build_server_stack,
    shutdown_stack,
)


CONFIG_PATH = Path(__file__).parents[2] / "config" / "server.json"


def make_test_config(tmp_path, *, reconnect_grace_seconds=20):
    document = copy.deepcopy(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    document["database"]["path"] = str(tmp_path / "reconnect-e2e.sqlite3")
    document["database"]["backup_directory"] = str(tmp_path / "backups")
    document["logging"]["server_path"] = str(tmp_path / "server.jsonl")
    document["logging"]["client_path"] = str(tmp_path / "client.jsonl")
    document["security"]["scrypt_n"] = 1024
    document["timing"]["reconnect_grace_seconds"] = reconnect_grace_seconds
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


def collect_messages(transport, *, duration=2.0):
    types = []
    deadline = time.time() + duration
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            message = transport.receive(timeout=min(0.2, remaining))
        except Empty:
            continue
        types.append(message.type)
    return types


def receive_push(transport, *message_types, timeout=2.0):
    buffered = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        if buffered:
            message = buffered.pop(0)
        else:
            message = transport.receive(timeout=remaining)
        if message.type in message_types:
            return message
        buffered.append(message)
    raise AssertionError(
        f"Timed out waiting for push types {message_types!r}; "
        f"buffered={[message.type for message in buffered]}"
    )


def matched_players(uri, policy, stack):
    first = WebSocketClientTransport(uri, policy)
    second = WebSocketClientTransport(uri, policy)
    first_auth = register_and_login(first, "First", "first-register", policy=policy)
    second_auth = register_and_login(second, "Second", "second-register", policy=policy)
    request(
        first,
        MessageType.PLAY_QUEUE_JOIN.value,
        {"auth_token": first_auth},
        "first-queue",
        policy=policy,
    )
    matched = request(
        second,
        MessageType.PLAY_QUEUE_JOIN.value,
        {"auth_token": second_auth},
        "second-queue",
        policy=policy,
    )
    first_match = request(
        first,
        MessageType.PLAY_QUEUE_STATUS.value,
        {"auth_token": first_auth},
        "first-status",
        policy=policy,
    ).payload
    game_id = matched.payload["game_id"]
    assert stack.registry.get(game_id) is not None
    return {
        "first": first,
        "second": second,
        "first_auth": first_auth,
        "second_auth": second_auth,
        "first_match": first_match,
        "second_match": matched.payload,
        "game_id": game_id,
    }


def bind_players(players, policy):
    for label, match_payload, auth in (
        ("first", players["first_match"], players["first_auth"]),
        ("second", players["second_match"], players["second_auth"]),
    ):
        response = request(
            players[label],
            MessageType.RESYNC_REQUEST.value,
            {
                "auth_token": auth,
                "game_token": match_payload["game_token"],
                "game_id": players["game_id"],
            },
            f"{label}-resync",
            policy=policy,
        )
        assert response.type == MessageType.SNAPSHOT.value


def record_meaningful_move(players, policy):
    white_match = (
        players["first_match"]
        if players["first_match"]["color"] == "w"
        else players["second_match"]
    )
    white_label = "first" if players["first_match"]["color"] == "w" else "second"
    white_auth = players[f"{white_label}_auth"]
    white_transport = players[white_label]
    snapshot = request(
        white_transport,
        MessageType.RESYNC_REQUEST.value,
        {
            "auth_token": white_auth,
            "game_token": white_match["game_token"],
            "game_id": players["game_id"],
        },
        "white-resync-for-move",
        policy=policy,
    )
    pawn = next(
        piece
        for piece in snapshot.payload["pieces"]
        if piece["row"] == 6 and piece["col"] == 0 and piece["token"] == "wP"
    )
    moved = request(
        white_transport,
        MessageType.MOVE_REQUEST.value,
        {
            "auth_token": white_auth,
            "game_token": white_match["game_token"],
            "game_id": players["game_id"],
            "piece_id": pawn["piece_id"],
            "expected_from": {"row": 6, "col": 0},
            "target": {"row": 4, "col": 0},
        },
        "meaningful-move",
        policy=policy,
    )
    assert moved.payload["accepted"] is True, moved.payload


def test_websocket_close_pushes_disconnect_countdown_to_opponent(tmp_path):
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
        players = None
        try:
            players = await asyncio.to_thread(matched_players, uri, policy, stack)
            await asyncio.to_thread(bind_players, players, policy)
            await asyncio.to_thread(players["first"].close)
            await asyncio.sleep(0.2)
            pushed = await asyncio.to_thread(
                receive_push,
                players["second"],
                MessageType.DISCONNECT_COUNTDOWN.value,
            )
            assert pushed.type == MessageType.DISCONNECT_COUNTDOWN.value
            assert pushed.payload["game_id"] == players["game_id"]
            assert pushed.payload["state"] == "PAUSED_FOR_RECONNECT"
            assert pushed.payload["remaining_ms"] > 0
        finally:
            if players is not None:
                players["first"].close()
                players["second"].close()
            await shutdown_stack(stack)

    asyncio.run(scenario())


def test_disconnect_reconnect_resumes_active_game(tmp_path):
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
        players = None
        try:
            players = await asyncio.to_thread(matched_players, uri, policy, stack)
            await asyncio.to_thread(bind_players, players, policy)
            disconnected_match = players["first_match"]
            disconnected_auth = players["first_auth"]
            await asyncio.to_thread(players["first"].close)
            await asyncio.sleep(0.2)

            pushed = await asyncio.to_thread(
                receive_push,
                players["second"],
                MessageType.DISCONNECT_COUNTDOWN.value,
            )
            assert pushed.type == MessageType.DISCONNECT_COUNTDOWN.value

            reconnected = WebSocketClientTransport(uri, policy)
            try:
                response = await asyncio.to_thread(
                    request,
                    reconnected,
                    MessageType.GAME_RECONNECT.value,
                    {
                        "auth_token": disconnected_auth,
                        "game_token": disconnected_match["game_token"],
                        "game_id": players["game_id"],
                    },
                    "reconnect",
                    policy=policy,
                )
                assert response.type == MessageType.GAME_LIFECYCLE_STATUS.value
                assert response.payload["state"] == "ACTIVE"
            finally:
                reconnected.close()
        finally:
            if players is not None:
                players["first"].close()
                players["second"].close()
            await shutdown_stack(stack)

    asyncio.run(scenario())


def active_player(players):
    if players["first_match"]["color"] == "w":
        return "first", "second"
    return "second", "first"


def test_disconnect_expiry_forfeits_after_grace(tmp_path):
    config = make_test_config(tmp_path, reconnect_grace_seconds=2)
    stack = build_server_stack(config)
    policy = EnvelopePolicy(
        config.network.protocol_version,
        config.network.max_message_bytes,
        config.network.request_id_max_length,
        config.network.message_type_max_length,
    )

    async def scenario():
        server = await stack.gateway.start("127.0.0.1", 0)
        stack.start_background_tasks()
        port = server.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        players = None
        try:
            players = await asyncio.to_thread(matched_players, uri, policy, stack)
            await asyncio.to_thread(bind_players, players, policy)
            assert len(stack.game_connections.connections_for(players["game_id"])) == 2
            await asyncio.to_thread(record_meaningful_move, players, policy)
            disconnected_label, opponent_label = active_player(players)
            disconnected = await asyncio.to_thread(
                request,
                players[disconnected_label],
                MessageType.GAME_DISCONNECT.value,
                {
                    "auth_token": players[f"{disconnected_label}_auth"],
                    "game_token": players[f"{disconnected_label}_match"]["game_token"],
                    "game_id": players["game_id"],
                },
                "explicit-disconnect",
                policy=policy,
            )
            assert disconnected.type == MessageType.DISCONNECT_COUNTDOWN.value, (
                disconnected.payload
            )
            grace_deadline = int(disconnected.payload["reconnect_deadline_ms"])
            await asyncio.sleep(max(0.0, (grace_deadline - int(time.time() * 1000) + 500) / 1000))
            collected = await asyncio.to_thread(
                collect_messages, players[opponent_label], duration=3.0
            )
            assert MessageType.DISCONNECT_COUNTDOWN.value in collected, collected
            assert MessageType.GAME_FORFEIT.value in collected, collected
        finally:
            if players is not None:
                players["first"].close()
                players["second"].close()
            await shutdown_stack(stack)

    asyncio.run(scenario())
