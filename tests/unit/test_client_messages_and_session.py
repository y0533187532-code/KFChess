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
        messages.resync(token, "game-secret", "game-1"),
        messages.lifecycle_status(token, "game-secret", "game-1"),
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
        "resync_request",
        "game_lifecycle_status",
    ]
    assert all(item.payload["auth_token"] == token for item in requests)
    assert all(item.payload["code"] == "ABC234" for item in requests[6:9])
    assert requests[-2].payload["game_token"] == "game-secret"
    assert requests[-1].payload["game_id"] == "game-1"


def test_gameplay_message_payloads_keep_existing_structured_contract():
    messages = factory()

    moved = messages.move(
        "auth", "game-token", "game-1", 7, (6, 0), (4, 0)
    )
    jumped = messages.jump("auth", "game-token", "game-1", 7, (6, 0))

    assert moved.type == "move_request"
    assert moved.payload == {
        "auth_token": "auth",
        "game_token": "game-token",
        "game_id": "game-1",
        "piece_id": 7,
        "expected_from": {"row": 6, "col": 0},
        "target": {"row": 4, "col": 0},
    }
    assert jumped.type == "jump_request"
    assert jumped.payload["target"] == jumped.payload["expected_from"]


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
    assert "room-token" not in repr(session)

    status = dict(room)
    status.update(status="ACTIVE", player_count=2, gameplay_started=True)
    status.pop("game_token")
    session.store_room(status)
    assert session.room.status == "ACTIVE"
    assert session.game.game_token == "room-token"

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
    assert session.room.color is None
    assert session.game.role == "SPECTATOR"
    assert session.game.seat is None
    assert session.game.color is None
    assert "spectator-token" not in repr(session)

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
