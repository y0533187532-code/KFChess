from types import SimpleNamespace

import numpy as np

from kongfu_chess.engine import GameSnapshot, PieceSnapshot
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


def test_renderer_covers_queue_and_match_found_without_drawing_tokens(monkeypatch):
    renderer = OpenCvClientRenderer(ClientLocalizer())
    session = authenticated_session()
    rendered_text = []
    monkeypatch.setattr(
        "kongfu_chess.client.screen_renderer.cv2.putText",
        lambda _frame, value, *_args: rendered_text.append(str(value)),
    )
    state = ClientUiState(
        screen=ClientScreen.PLAY_QUEUE,
        queue_enqueued_at_ms=1000,
        queue_expires_at_ms=62000,
        now_ms=2000,
    )
    queue = renderer.render(state, session)
    assert queue.any()
    assert state.queue_seconds_elapsed == 1
    assert state.queue_seconds_remaining == 60
    assert "Waiting..." in rendered_text
    assert "Waiting time: 1s" in rendered_text
    assert renderer.hit_test(400, 390).value is UiAction.PLAY_CANCEL

    rendered_text.clear()
    session.store_play_match(
        {
            "game_id": "game-1",
            "game_token": "never-render-this-game-token",
            "role": "PLAYER",
            "seat": "FIRST_PLAYER",
            "color": "w",
            "mode": "PLAY",
            "ranked": True,
        }
    )
    state.screen = ClientScreen.MATCH_FOUND
    found = renderer.render(state, session)
    assert found.any()
    assert "Role: Player" in rendered_text
    assert "Seat: First player / Color: White" in rendered_text
    assert all("never-render" not in value for value in rendered_text)
    assert "never-render" not in repr(session)


def test_renderer_covers_room_entry_player_and_spectator_lobbies(monkeypatch):
    renderer = OpenCvClientRenderer(ClientLocalizer())
    session = authenticated_session()
    rendered_text = []
    monkeypatch.setattr(
        "kongfu_chess.client.screen_renderer.cv2.putText",
        lambda _frame, value, *_args: rendered_text.append(str(value)),
    )
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
        "status": "WAITING",
        "role": "PLAYER",
        "seat": "FIRST_PLAYER",
        "color": "w",
        "game_token": "room-token",
        "player_count": 1,
        "spectator_count": 0,
        "gameplay_started": False,
    }
    session.store_room(base_room)
    state.screen = ClientScreen.ROOM_LOBBY
    player = renderer.render(state, session)
    assert player.any()
    assert "Room code: ABC234" in rendered_text
    assert "Status: Waiting" in rendered_text
    assert "Role: Player" in rendered_text
    assert "Seat: First player / Color: White" in rendered_text
    assert "Waiting for an opponent..." in rendered_text
    assert renderer.hit_test(300, 490).value is UiAction.ROOM_REFRESH
    assert renderer.hit_test(550, 490).value is UiAction.ROOM_LEAVE

    rendered_text.clear()
    spectator = dict(base_room)
    spectator.update(
        status="ACTIVE",
        role="SPECTATOR",
        player_count=2,
        spectator_count=1,
        gameplay_started=True,
        game_token="spectator-token",
    )
    spectator.pop("seat")
    spectator.pop("color")
    session.store_room(spectator)
    assert renderer.render(state, session).any()
    assert "Status: Active" in rendered_text
    assert "Role: Spectator" in rendered_text
    assert "Spectator (no player color)" in rendered_text
    assert all("spectator-token" not in value for value in rendered_text)


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


class FakeGameView:
    def __init__(self):
        self.snapshots = []

    def render(self, snapshot):
        self.snapshots.append(snapshot)
        return SimpleNamespace(
            img=np.full((995, 1390, 4), 100, dtype=np.uint8)
        )


def test_renderer_draws_authoritative_board_identity_and_reconnect_status(
    monkeypatch,
):
    game_view = FakeGameView()
    renderer = OpenCvClientRenderer(ClientLocalizer(), game_view=game_view)
    session = authenticated_session()
    session.store_play_match(
        {
            "game_id": "game-1",
            "game_token": "never-render-game-token",
            "role": "PLAYER",
            "seat": "SECOND_PLAYER",
            "color": "b",
            "mode": "PLAY",
            "ranked": True,
        }
    )
    snapshot = GameSnapshot(
        8,
        8,
        False,
        pieces=(PieceSnapshot(1, 0, "bP", 8),),
    )
    state = ClientUiState(
        screen=ClientScreen.GAME_BOARD,
        game_snapshot=snapshot,
        game_lifecycle_state="PAUSED_FOR_RECONNECT",
        game_reconnect_deadline_ms=23000,
        game_selected_cell=(1, 0),
        now_ms=4000,
    )
    rendered_text = []
    monkeypatch.setattr(
        "kongfu_chess.client.screen_renderer.cv2.putText",
        lambda _frame, value, *_args: rendered_text.append(str(value)),
    )

    frame = renderer.render(state, session)

    assert frame.shape == (995, 1390, 4)
    assert game_view.snapshots == [snapshot]
    assert "Real-time play" in rendered_text
    assert "Seat: Second player / Color: Black" in rendered_text
    assert "Paused for reconnect: 19s remaining" in rendered_text
    assert renderer.hit_test(300, 200).kind == "board_cell"
    assert renderer.hit_test(300, 200).value == (1, 0)
    assert all("never-render" not in text for text in rendered_text)


def test_renderer_shows_game_over_banner_and_leave_button(monkeypatch):
    game_view = FakeGameView()
    renderer = OpenCvClientRenderer(ClientLocalizer(), game_view=game_view)
    session = authenticated_session()
    session.store_play_match(
        {
            "game_id": "game-1",
            "game_token": "token",
            "role": "PLAYER",
            "seat": "FIRST_PLAYER",
            "color": "w",
            "mode": "PLAY",
            "ranked": True,
        }
    )
    snapshot = GameSnapshot(8, 8, True, pieces=())
    state = ClientUiState(
        screen=ClientScreen.GAME_BOARD,
        game_snapshot=snapshot,
        game_lifecycle_state="ENDED",
        inline_message="You won the game.",
    )
    rendered_text = []
    monkeypatch.setattr(
        "kongfu_chess.client.screen_renderer.cv2.putText",
        lambda _frame, value, *_args: rendered_text.append(str(value)),
    )

    renderer.render(state, session)

    assert "GAME OVER" in rendered_text
    assert "Leave game" in rendered_text
    assert "You won the game." in rendered_text


def test_renderer_leave_confirm_overlay_exposes_confirm_and_cancel_actions():
    renderer = OpenCvClientRenderer(ClientLocalizer(), game_view=FakeGameView())
    session = authenticated_session()
    session.store_play_match(
        {
            "game_id": "game-1",
            "game_token": "token",
            "role": "PLAYER",
            "seat": "FIRST_PLAYER",
            "color": "w",
            "mode": "PLAY",
            "ranked": True,
        }
    )
    state = ClientUiState(
        screen=ClientScreen.GAME_BOARD,
        game_snapshot=GameSnapshot(8, 8, False, pieces=()),
        game_lifecycle_state="ACTIVE",
        game_leave_confirm_pending=True,
    )

    renderer.render(state, session)

    confirm_hit = renderer.hit_test(515, 439)
    cancel_hit = renderer.hit_test(755, 439)
    assert confirm_hit.value is UiAction.GAME_LEAVE_CONFIRM
    assert cancel_hit.value is UiAction.GAME_LEAVE_CANCEL
