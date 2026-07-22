import asyncio
import copy
import json
from pathlib import Path

from kongfu_chess.client import WebSocketClientTransport
from kongfu_chess.infrastructure.configuration import ConfigProvider
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope, MessageType
from kongfu_chess.server import (
    build_server_stack,
    shutdown_stack,
)


CONFIG_PATH = Path(__file__).parents[2] / "config" / "server.json"


def make_test_config(tmp_path):
    document = copy.deepcopy(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    document["database"]["path"] = str(tmp_path / "server-stack.sqlite3")
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


def run_two_client_match(uri, policy, stack):
    white = WebSocketClientTransport(uri, policy)
    black = WebSocketClientTransport(uri, policy)
    try:
        white_auth = register_and_login(white, "White", "white-register", policy=policy)
        black_auth = register_and_login(black, "Black", "black-register", policy=policy)

        queued = request(
            white,
            MessageType.PLAY_QUEUE_JOIN.value,
            {"auth_token": white_auth},
            "white-queue",
            policy=policy,
        )
        assert queued.payload["state"] == "queued"

        matched = request(
            black,
            MessageType.PLAY_QUEUE_JOIN.value,
            {"auth_token": black_auth},
            "black-queue",
            policy=policy,
        )
        assert matched.type == MessageType.PLAY_MATCH_FOUND.value
        game_id = matched.payload["game_id"]
        assert stack.registry.get(game_id) is not None

        white_status = request(
            white,
            MessageType.PLAY_QUEUE_STATUS.value,
            {"auth_token": white_auth},
            "white-status",
            policy=policy,
        )
        white_match = white_status.payload
        black_match = matched.payload
        assert white_match["game_id"] == game_id
        assert black_match["game_id"] == game_id

        if white_match["color"] == "w":
            mover, mover_auth, mover_match = white, white_auth, white_match
            observer = black
        else:
            mover, mover_auth, mover_match = black, black_auth, black_match
            observer = white

        mover_resync = request(
            mover,
            MessageType.RESYNC_REQUEST.value,
            {
                "auth_token": mover_auth,
                "game_token": mover_match["game_token"],
                "game_id": game_id,
            },
            "mover-resync",
            policy=policy,
        )
        assert mover_resync.type == MessageType.SNAPSHOT.value

        observer_auth = black_auth if observer is black else white_auth
        observer_match = black_match if observer is black else white_match
        observer_resync = request(
            observer,
            MessageType.RESYNC_REQUEST.value,
            {
                "auth_token": observer_auth,
                "game_token": observer_match["game_token"],
                "game_id": game_id,
            },
            "observer-resync",
            policy=policy,
        )
        assert observer_resync.type == MessageType.SNAPSHOT.value

        pawn = next(
            piece
            for piece in mover_resync.payload["pieces"]
            if piece["row"] == 6 and piece["col"] == 0 and piece["token"] == "wP"
        )
        moved = request(
            mover,
            MessageType.MOVE_REQUEST.value,
            {
                "auth_token": mover_auth,
                "game_token": mover_match["game_token"],
                "game_id": game_id,
                "piece_id": pawn["piece_id"],
                "expected_from": {"row": 6, "col": 0},
                "target": {"row": 4, "col": 0},
            },
            "mover-move",
            policy=policy,
        )
        assert moved.payload["accepted"] is True, moved.payload

        pushed = observer.receive(timeout=2.0)
        assert pushed.type == MessageType.STATE_UPDATE.value
        assert pushed.payload["game_id"] == game_id
        assert pushed.payload["sequence"] == moved.payload["sequence"]
        assert pushed.payload["snapshot"]["board_width"] == 8
    finally:
        white.close()
        black.close()


def test_server_stack_registers_runtime_on_match_and_pushes_state_updates(tmp_path):
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
        try:
            await asyncio.to_thread(run_two_client_match, uri, policy, stack)
        finally:
            await shutdown_stack(stack)

    asyncio.run(scenario())
