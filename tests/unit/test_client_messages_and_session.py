from types import SimpleNamespace

import pytest

from kongfu_chess.client import (
    ClientMessageFactory,
    ClientSessionState,
    ClientUiConstraints,
)
from kongfu_chess.protocol import EnvelopePolicy


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


def factory():
    identifiers = iter(f"request-{index}" for index in range(20))
    return ClientMessageFactory(
        POLICY,
        clock_ms=lambda: 1234,
        request_id_factory=lambda: next(identifiers),
    )


def test_auth_message_payloads_use_shared_envelope():
    messages = factory()

    login = messages.login("Dana", "secret7")
    register = messages.register(
        "Dana", "secret7", "Dana@Example.Test", "+972501234567"
    )

    assert login.type == "login_request"
    assert login.request_id == "request-0"
    assert login.timestamp_ms == 1234
    assert dict(login.payload) == {"username": "Dana", "password": "secret7"}
    assert register.type == "register_request"
    assert dict(register.payload) == {
        "username": "Dana",
        "password": "secret7",
        "email": "Dana@Example.Test",
        "phone": "+972501234567",
    }


def test_authenticated_payloads_include_auth_and_normalize_room_codes():
    messages = factory()
    token = "auth-secret"

    requests = (
        messages.logout(token),
        messages.validate_auth(token),
        messages.play_join(token),
        messages.play_cancel(token),
        messages.play_status(token),
        messages.room_create(token),
        messages.room_join(token, "abc234"),
        messages.room_leave(token, "abc234"),
        messages.room_status(token, "abc234"),
    )

    assert [item.type for item in requests] == [
        "logout_request",
        "validate_auth_request",
        "play_queue_join",
        "play_queue_cancel",
        "play_queue_status",
        "room_create",
        "room_join",
        "room_leave",
        "room_status",
    ]
    assert all(item.payload["auth_token"] == token for item in requests)
    assert all(item.payload["code"] == "ABC234" for item in requests[-3:])


def test_client_session_stores_play_identity_and_redacts_tokens():
    session = ClientSessionState()
    session.authenticate(
        {
            "user_id": 7,
            "username": "Dana",
            "rating": 1200,
            "auth_token": "raw-auth-token",
            "expires_at_ms": 9000,
        }
    )
    session.store_play_match(
        {
            "game_id": "game-1",
            "game_token": "raw-game-token",
            "role": "PLAYER",
            "seat": "FIRST_PLAYER",
            "color": "w",
            "ranked": True,
            "mode": "PLAY",
        }
    )

    assert session.authenticated is True
    assert session.require_auth_token() == "raw-auth-token"
    assert session.game.seat == "FIRST_PLAYER"
    assert session.game.role == "PLAYER"
    assert session.game.color == "w"
    assert "raw-auth-token" not in repr(session)
    assert "raw-game-token" not in repr(session)


def test_client_session_refreshes_validated_principal_without_replacing_token():
    session = ClientSessionState()
    session.authenticate(
        {
            "user_id": 7,
            "username": "Dana",
            "rating": 1200,
            "auth_token": "raw-auth-token",
            "expires_at_ms": 9000,
        }
    )

    session.refresh_principal({"user_id": 7, "username": "Dana", "rating": 1216})

    assert session.rating == 1216
    assert session.expires_at_ms == 9000
    assert session.require_auth_token() == "raw-auth-token"


def test_client_session_tracks_player_and_spectator_rooms_then_clears():
    session = ClientSessionState()
    session.authenticate(
        {
            "user_id": 7,
            "username": "Dana",
            "rating": 1200,
            "auth_token": "auth",
            "expires_at_ms": 9000,
        }
    )
    room = {
        "room_id": 2,
        "code": "ABC234",
        "game_id": "room-game",
        "status": "WAITING",
        "role": "PLAYER",
        "seat": "FIRST_PLAYER",
        "color": "w",
        "game_token": "room-token",
        "player_count": 1,
        "spectator_count": 0,
        "gameplay_started": False,
    }
    session.store_room(room)

    assert session.room.code == "ABC234"
    assert session.game.mode == "ROOM"

    spectator = dict(room)
    spectator.update(
        role="SPECTATOR",
        player_count=2,
        spectator_count=1,
        game_token="spectator-token",
    )
    spectator.pop("seat")
    spectator.pop("color")
    session.store_room(spectator)
    assert session.room.seat is None
    assert session.game.role == "SPECTATOR"

    session.clear_room()
    assert session.room is None and session.game is None
    session.clear()
    assert session.authenticated is False
    with pytest.raises(RuntimeError, match="Authentication"):
        session.require_auth_token()


def test_client_constraints_are_loaded_from_server_security_config():
    config = SimpleNamespace(
        security=SimpleNamespace(
            username_min_length=3,
            username_max_length=20,
            password_min_length=6,
        )
    )

    constraints = ClientUiConstraints.from_config(config)

    assert constraints == ClientUiConstraints(3, 20, 6)
