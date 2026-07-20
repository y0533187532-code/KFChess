import asyncio

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
    AuthHandlers,
    AuthService,
    MessageRouter,
    PasswordHasher,
    RequestContext,
)


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


def routed_auth(tmp_path):
    database = SqliteDatabase(tmp_path / "routing.sqlite3", busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    tokens = TokenService(
        AuthSessionRepository(database), GameTokenRepository(database), token_bytes=32
    )
    service = AuthService(
        users,
        tokens,
        PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32),
        password_min_length=6,
        initial_rating=1200,
        auth_token_ttl_seconds=60,
    )
    router = MessageRouter()
    AuthHandlers(service, clock_ms=lambda: 1000).register_routes(router)
    return router


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


def test_auth_routes_register_login_validate_logout_without_ui(tmp_path):
    router = routed_auth(tmp_path)
    registered = route(
        router,
        "register_request",
        {
            "username": "Dana",
            "password": "secret7",
            "email": "Dana@Example.Test",
            "phone": "0501234567",
        },
    )
    logged_in = route(
        router,
        "login_request",
        {"username": "Dana", "password": "secret7"},
        "request-2",
    )
    token = logged_in.payload["auth_token"]
    validated = route(
        router, "validate_auth_request", {"auth_token": token}, "request-3"
    )
    logged_out = route(
        router, "logout_request", {"auth_token": token}, "request-4"
    )

    assert registered.payload == {
        "accepted": True, "code": "ok", "user_id": 1,
        "username": "Dana", "rating": 1200,
    }
    assert logged_in.payload["accepted"] is True
    assert validated.payload["username"] == "Dana"
    assert "auth_token" not in registered.payload
    assert "auth_token" not in validated.payload
    assert logged_out.payload == {"accepted": True, "code": "ok"}


def test_auth_route_maps_service_failure_and_rejects_wrong_payload_schema(tmp_path):
    router = routed_auth(tmp_path)

    failed = route(
        router,
        "login_request",
        {"username": "missing", "password": "secret7"},
    )
    assert failed.payload == {"accepted": False, "code": "invalid_credentials"}

    with pytest.raises(ProtocolError) as raised:
        route(
            router,
            "login_request",
            {"username": "Dana", "password": "secret7", "extra": "no"},
        )
    assert raised.value.code.value == "invalid_field"
