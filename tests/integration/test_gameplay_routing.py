import asyncio
from types import SimpleNamespace

import pytest

from kongfu_chess.engine import GameSnapshot, MoveResult, PieceSnapshot
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope, ProtocolError
from kongfu_chess.server import (
    GameplayCommandService,
    GameplayHandlers,
    GameSessionRegistry,
    MessageRouter,
    RequestContext,
    build_game_session,
)


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


class Auth:
    def validate_auth_token(self, token, *, now_ms):
        return SimpleNamespace(user_id=1)


class Tokens:
    def __init__(self, role="PLAYER", color="w"):
        self.role = role
        self.color = color

    def verify_game(self, token, *, game_id, now_ms):
        return SimpleNamespace(user_id=1, role=self.role, color=self.color)


class Engine:
    def __init__(self):
        self.moves = []
        self.jumps = []

    def snapshot(self):
        return GameSnapshot(
            8,
            8,
            False,
            pieces=(PieceSnapshot(1, 4, "wP", 7),),
        )

    def request_move(self, *coordinates):
        self.moves.append(coordinates)
        return MoveResult(True, "ok")

    def request_jump(self, *coordinates):
        self.jumps.append(coordinates)
        return MoveResult(True, "ok")


def envelope(message_type, payload, request_id="request-1"):
    return MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": message_type,
            "request_id": request_id,
            "timestamp_ms": 1,
            "payload": payload,
        },
        POLICY,
    )


def payload(*, target=None):
    return {
        "auth_token": "auth",
        "game_token": "game-token",
        "game_id": "game-1",
        "piece_id": 7,
        "expected_from": {"row": 1, "col": 4},
        "target": target or {"row": 3, "col": 4},
    }


def test_structured_move_and_jump_routes_return_authoritative_sequences():
    async def scenario():
        engine = Engine()
        session = build_game_session(
            "game-1", engine, initial_sequence=4, request_cache_size=16
        )
        session.start()
        sessions = GameSessionRegistry()
        sessions.register(session)
        router = MessageRouter()
        GameplayHandlers(
            GameplayCommandService(Auth(), Tokens(), sessions),
            clock_ms=lambda: 1000,
        ).register_routes(router)

        moved = await router.route(
            RequestContext("connection-1", envelope("move_request", payload()))
        )
        invalid_jump = await router.route(
            RequestContext(
                "connection-1",
                envelope("jump_request", payload(), "request-2"),
            )
        )
        valid_jump = await router.route(
            RequestContext(
                "connection-1",
                envelope(
                    "jump_request",
                    payload(target={"row": 1, "col": 4}),
                    "request-3",
                ),
            )
        )
        snapshot = await router.route(
            RequestContext(
                "connection-1",
                envelope(
                    "resync_request",
                    {
                        "auth_token": "auth",
                        "game_token": "game-token",
                        "game_id": "game-1",
                    },
                    "request-4",
                ),
            )
        )
        await session.close()
        return engine, moved, invalid_jump, valid_jump, snapshot

    engine, moved, invalid_jump, valid_jump, snapshot = asyncio.run(scenario())

    assert moved.payload["accepted"] is True
    assert moved.payload["code"] == "ok"
    assert moved.payload["sequence"] == 5
    assert moved.payload["piece_id"] == 7
    assert "snapshot" in moved.payload
    assert invalid_jump.payload["code"] == "invalid_field"
    assert invalid_jump.payload["sequence"] == 5
    assert valid_jump.payload["sequence"] == 6
    assert engine.moves == [(1, 4, 3, 4)]
    assert engine.jumps == [(1, 4)]
    assert snapshot.type == "snapshot"
    assert snapshot.payload["board_width"] == 8
    assert snapshot.payload["pieces"] == [
        {
            "row": 1,
            "col": 4,
            "token": "wP",
            "piece_id": 7,
            "state": "idle",
            "rest_remaining_ms": None,
        }
    ]
    assert "auth_token" not in snapshot.payload
    assert "game_token" not in snapshot.payload


def test_gameplay_route_rejects_payload_without_required_target():
    router = MessageRouter()
    GameplayHandlers(object(), clock_ms=lambda: 1000).register_routes(router)
    invalid_payload = payload()
    invalid_payload.pop("target")

    with pytest.raises(ProtocolError) as raised:
        asyncio.run(
            router.route(
                RequestContext(
                    "connection-1",
                    envelope("move_request", invalid_payload),
                )
            )
        )

    assert raised.value.code.value == "invalid_field"


def test_resync_route_rejects_payload_outside_the_approved_contract():
    router = MessageRouter()
    GameplayHandlers(object(), clock_ms=lambda: 1000).register_routes(router)

    with pytest.raises(ProtocolError) as raised:
        asyncio.run(
            router.route(
                RequestContext(
                    "connection-1",
                    envelope(
                        "resync_request",
                        {
                            "auth_token": "auth",
                            "game_token": "game-token",
                        },
                    ),
                )
            )
        )

    assert raised.value.code.value == "invalid_field"


def test_resync_allows_authorized_colorless_room_spectator():
    async def scenario():
        session = build_game_session(
            "game-1", Engine(), initial_sequence=0, request_cache_size=16
        )
        session.start()
        sessions = GameSessionRegistry()
        sessions.register(session)
        router = MessageRouter()
        GameplayHandlers(
            GameplayCommandService(
                Auth(), Tokens(role="SPECTATOR", color=None), sessions
            ),
            clock_ms=lambda: 1000,
        ).register_routes(router)
        result = await router.route(
            RequestContext(
                "connection-1",
                envelope(
                    "resync_request",
                    {
                        "auth_token": "auth",
                        "game_token": "spectator-token",
                        "game_id": "game-1",
                    },
                ),
            )
        )
        await session.close()
        return result

    result = asyncio.run(scenario())

    assert result.type == "snapshot"
    assert result.payload["pieces"][0]["piece_id"] == 7
