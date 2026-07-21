from types import SimpleNamespace

import numpy as np

from kongfu_chess.client import (
    ClientLocalizer,
    ClientScreen,
    ClientSessionState,
    ClientUiState,
    OpenCvClientRenderer,
    UiAction,
    UiRect,
)


def authenticated_session():
    session = ClientSessionState()
    session.authenticate(
        {
            "user_id": 7,
            "username": "Dana",
            "rating": 1200,
            "auth_token": "never-render-this-auth-token",
            "expires_at_ms": 9000,
        }
    )
    return session


def test_rect_boundaries_and_renderer_login_hit_targets():
    rectangle = UiRect(10, 20, 30, 40)
    assert rectangle.contains(10, 20)
    assert rectangle.contains(39, 59)
    assert not rectangle.contains(40, 60)

    renderer = OpenCvClientRenderer(ClientLocalizer())
    state = ClientUiState()
    state.fields["password"] = "secret7"
    frame = renderer.render(state, ClientSessionState())

    assert frame.shape == (renderer.HEIGHT, renderer.WIDTH, 3)
    assert frame.dtype == np.uint8
    assert state.display_value("password") == "*******"
    assert renderer.hit_test(250, 250).value == "password"
    assert renderer.hit_test(250, 330).value is UiAction.SUBMIT_LOGIN
    assert renderer.hit_test(5, 5) is None


def test_renderer_covers_registration_and_main_menu_screens():
    renderer = OpenCvClientRenderer(ClientLocalizer())
    session = authenticated_session()
    state = ClientUiState(screen=ClientScreen.REGISTER)
    state.active_field = "email"
    state.inline_message = "inline error"
    state.loading = True

    register = renderer.render(state, session)
    assert register.any()
    assert renderer.hit_test(250, 335).value == "email"
    assert renderer.hit_test(510, 480).value is UiAction.SHOW_LOGIN

    state.screen = ClientScreen.MAIN_MENU
    state.loading = False
    main = renderer.render(state, session)
    assert main.any()
    assert renderer.hit_test(400, 320).value is UiAction.PLAY
    assert renderer.hit_test(400, 390).value is UiAction.ROOM
    assert renderer.hit_test(400, 455).value is UiAction.LOGOUT


def test_renderer_covers_queue_and_match_found_without_drawing_tokens():
    renderer = OpenCvClientRenderer(ClientLocalizer())
    session = authenticated_session()
    state = ClientUiState(
        screen=ClientScreen.PLAY_QUEUE,
        queue_expires_at_ms=62000,
        now_ms=2000,
    )
    queue = renderer.render(state, session)
    assert queue.any()
    assert state.queue_seconds_remaining == 60
    assert renderer.hit_test(400, 390).value is UiAction.PLAY_CANCEL

    session.store_play_match(
        {
            "game_id": "game-1",
            "game_token": "never-render-this-game-token",
            "color": "w",
            "mode": "PLAY",
            "ranked": True,
        }
    )
    state.screen = ClientScreen.MATCH_FOUND
    found = renderer.render(state, session)
    assert found.any()
    assert "never-render" not in repr(session)


def test_renderer_covers_room_entry_player_and_spectator_lobbies():
    renderer = OpenCvClientRenderer(ClientLocalizer())
    session = authenticated_session()
    state = ClientUiState(screen=ClientScreen.ROOM_ENTRY)
    entry = renderer.render(state, session)
    assert entry.any()
    assert renderer.hit_test(300, 230).value is UiAction.ROOM_CREATE
    assert renderer.hit_test(300, 410).value is UiAction.ROOM_JOIN
    assert renderer.hit_test(550, 410).value is UiAction.ROOM_CANCEL

    base_room = {
        "room_id": 2,
        "code": "ABC234",
        "game_id": "room-game",
        "status": "ACTIVE",
        "role": "PLAYER",
        "seat": "FIRST_PLAYER",
        "color": "w",
        "game_token": "room-token",
        "player_count": 2,
        "spectator_count": 0,
        "gameplay_started": True,
    }
    session.store_room(base_room)
    state.screen = ClientScreen.ROOM_LOBBY
    player = renderer.render(state, session)
    assert player.any()
    assert renderer.hit_test(300, 490).value is UiAction.ROOM_REFRESH
    assert renderer.hit_test(550, 490).value is UiAction.ROOM_LEAVE

    spectator = dict(base_room)
    spectator.update(role="SPECTATOR", spectator_count=1)
    spectator.pop("seat")
    spectator.pop("color")
    session.store_room(spectator)
    assert renderer.render(state, session).any()


def test_renderer_handles_missing_room_and_zero_queue_deadline():
    renderer = OpenCvClientRenderer(ClientLocalizer())
    state = ClientUiState(
        screen=ClientScreen.PLAY_QUEUE,
        queue_expires_at_ms=1000,
        now_ms=2000,
    )
    assert state.queue_seconds_remaining == 0
    assert renderer.render(state, ClientSessionState()).any()

    state.screen = ClientScreen.ROOM_LOBBY
    assert renderer.render(state, ClientSessionState()).any()
