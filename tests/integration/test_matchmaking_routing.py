import asyncio
import json

import pytest

from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameTokenRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope, ProtocolError
from kongfu_chess.server import (
    AuthService,
    MatchmakingHandlers,
    MatchmakingService,
    MessageRouter,
    PasswordHasher,
    RequestContext,
)


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


def routed_matchmaking(tmp_path):
    database = SqliteDatabase(tmp_path / "matchmaking-routing.sqlite3", busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    tokens = TokenService(
        AuthSessionRepository(database), GameTokenRepository(database), token_bytes=32
    )
    auth = AuthService(
        users,
        tokens,
        PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32),
        password_min_length=6,
        initial_rating=1200,
        auth_token_ttl_seconds=600,
    )
    service = MatchmakingService(
        auth,
        tokens,
        rating_range=100,
        timeout_seconds=60,
        max_queue_users=200,
        seat_selector=lambda waiting, joining: (waiting, joining),
        game_id_factory=lambda: "routed-game",
    )
    current_time = {"ms": 2000}
    router = MessageRouter()
    MatchmakingHandlers(
        service, clock_ms=lambda: current_time["ms"]
    ).register_routes(router)
    return auth, router, current_time


def player(auth, username, *, now_ms):
    auth.register(
        username=username,
        password="secret7",
        email=f"{username}@example.test",
        phone="0501234567",
        now_ms=now_ms,
    )
    return auth.login(
        username=username, password="secret7", now_ms=now_ms + 1
    ).auth_token


def route(router, message_type, auth_token, request_id="request-1"):
    envelope = MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": message_type,
            "request_id": request_id,
            "timestamp_ms": 1,
            "payload": {"auth_token": auth_token},
        },
        POLICY,
    )
    return asyncio.run(router.route(RequestContext("connection-1", envelope)))


def test_join_and_status_route_each_players_own_match_token(tmp_path):
    auth, router, current_time = routed_matchmaking(tmp_path)
    first = player(auth, "First", now_ms=1000)
    second = player(auth, "Second", now_ms=1100)

    queued = route(router, "play_queue_join", first)
    current_time["ms"] = 2001
    joining_found = route(router, "play_queue_join", second, "request-2")
    current_time["ms"] = 2002
    waiting_found = route(router, "play_queue_status", first, "request-3")

    assert queued.type == "play_queue_status"
    assert queued.payload["state"] == "queued"
    assert "game_token" not in queued.payload
    assert joining_found.type == waiting_found.type == "play_match_found"
    assert joining_found.payload["game_id"] == waiting_found.payload["game_id"]
    assert joining_found.payload["game_token"] != waiting_found.payload["game_token"]
    assert joining_found.payload["role"] == waiting_found.payload["role"] == "PLAYER"
    assert joining_found.payload["seat"] == "SECOND_PLAYER"
    assert waiting_found.payload["seat"] == "FIRST_PLAYER"
    assert joining_found.payload["color"] == "b"
    assert waiting_found.payload["color"] == "w"
    assert joining_found.payload["ranked"] is True
    assert joining_found.payload["mode"] == "PLAY"
    assert waiting_found.payload["game_token"] not in json.dumps(
        dict(joining_found.payload)
    )


def test_cancel_and_timeout_have_dedicated_protocol_responses(tmp_path):
    auth, router, current_time = routed_matchmaking(tmp_path)
    token = player(auth, "Dana", now_ms=1000)

    route(router, "play_queue_join", token)
    cancelled = route(router, "play_queue_cancel", token, "request-2")
    assert cancelled.type == "play_queue_status"
    assert cancelled.payload["state"] == "idle"

    route(router, "play_queue_join", token, "request-3")
    current_time["ms"] = 62000
    timed_out = route(router, "play_queue_status", token, "request-4")
    assert timed_out.type == "matchmaking_timeout"
    assert timed_out.payload["code"] == "matchmaking_timeout"
    assert timed_out.payload["state"] == "timed_out"


def test_matchmaking_route_maps_auth_errors_and_validates_payload(tmp_path):
    _, router, _ = routed_matchmaking(tmp_path)

    failed = route(router, "play_queue_join", "invalid")
    assert failed.type == "command_result"
    assert failed.payload == {"accepted": False, "code": "invalid_token"}

    envelope = MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": "play_queue_join",
            "request_id": "bad-request",
            "timestamp_ms": 1,
            "payload": {"auth_token": "invalid", "extra": "field"},
        },
        POLICY,
    )
    with pytest.raises(ProtocolError) as raised:
        asyncio.run(router.route(RequestContext("connection-1", envelope)))
    assert raised.value.code.value == "invalid_field"
