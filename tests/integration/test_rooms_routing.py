import asyncio
import json

import pytest

from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameTokenRepository,
    RoomRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope, ProtocolError
from kongfu_chess.server import (
    AuthService,
    MessageRouter,
    PasswordHasher,
    RequestContext,
    RoomsHandlers,
    RoomsService,
)


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


def routed_rooms(tmp_path):
    database = SqliteDatabase(tmp_path / "rooms-routing.sqlite3", busy_timeout_ms=1000)
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
    service = RoomsService(
        auth,
        tokens,
        RoomRepository(database),
        max_spectators=10,
        max_open_rooms=100,
        code_factory=lambda: "ABC234",
        game_id_factory=lambda: "routed-room-game",
        snapshot_provider=lambda _game_id: {"sequence": 0},
    )
    router = MessageRouter()
    RoomsHandlers(service, clock_ms=lambda: 2000).register_routes(router)
    return auth, router


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


def route(router, message_type, payload, request_id="request-1"):
    envelope = MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": message_type,
            "request_id": request_id,
            "timestamp_ms": 1,
            "payload": payload,
        },
        POLICY,
    )
    return asyncio.run(router.route(RequestContext("connection-1", envelope)))


def test_room_routes_return_only_callers_new_token_and_boundary_color(tmp_path):
    auth, router = routed_rooms(tmp_path)
    creator = player(auth, "Creator", now_ms=1000)
    opponent = player(auth, "Opponent", now_ms=1100)
    spectator = player(auth, "Spectator", now_ms=1200)

    created = route(router, "room_create", {"auth_token": creator})
    joined = route(
        router,
        "room_join",
        {"auth_token": opponent, "code": created.payload["code"].lower()},
        "request-2",
    )
    watched = route(
        router,
        "room_join",
        {"auth_token": spectator, "code": created.payload["code"]},
        "request-3",
    )
    status = route(
        router,
        "room_status",
        {"auth_token": creator, "code": created.payload["code"]},
        "request-4",
    )

    assert created.type == joined.type == watched.type == status.type == "room_status"
    assert created.payload["seat"] == "FIRST_PLAYER"
    assert created.payload["color"] == "w"
    assert joined.payload["seat"] == "SECOND_PLAYER"
    assert joined.payload["color"] == "b"
    assert watched.payload["role"] == "SPECTATOR"
    assert "seat" not in watched.payload and "color" not in watched.payload
    assert watched.payload["snapshot"] == {"sequence": 0}
    assert len({
        created.payload["game_token"],
        joined.payload["game_token"],
        watched.payload["game_token"],
    }) == 3
    assert created.payload["game_token"] not in json.dumps(dict(joined.payload))
    assert joined.payload["game_token"] not in json.dumps(dict(watched.payload))
    assert "game_token" not in status.payload


def test_leave_response_has_no_token_and_errors_are_structured(tmp_path):
    auth, router = routed_rooms(tmp_path)
    creator = player(auth, "Creator", now_ms=1000)
    created = route(router, "room_create", {"auth_token": creator})
    left = route(
        router,
        "room_leave",
        {"auth_token": creator, "code": created.payload["code"]},
        "request-2",
    )
    failed = route(
        router,
        "room_join",
        {"auth_token": "invalid", "code": created.payload["code"]},
        "request-3",
    )

    assert left.payload["status"] == "CLOSED"
    assert "game_token" not in left.payload
    assert failed.type == "command_result"
    assert failed.payload == {"accepted": False, "code": "invalid_token"}


def test_room_routes_reject_extra_or_missing_payload_fields(tmp_path):
    _, router = routed_rooms(tmp_path)

    with pytest.raises(ProtocolError) as raised:
        route(
            router,
            "room_create",
            {"auth_token": "invalid", "extra": "field"},
        )
    assert raised.value.code.value == "invalid_field"

    with pytest.raises(ProtocolError) as raised:
        route(router, "room_join", {"auth_token": "invalid"}, "request-2")
    assert raised.value.code.value == "invalid_field"
