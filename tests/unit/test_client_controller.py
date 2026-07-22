from kongfu_chess.client import (
    ClientController,
    ClientLocalizer,
    ClientMessageFactory,
    ClientScreen,
    ClientSessionState,
    ClientUiConstraints,
    UiAction,
)
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope, MessageType


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


class Dispatcher:
    def __init__(self):
        self.sent = []

    def submit(self, envelope):
        self.sent.append(envelope)

    def send_immediate(self, envelope):
        self.sent.append(envelope)


def make_controller(*, localizer=None):
    dispatcher = Dispatcher()
    ids = iter(f"request-{index}" for index in range(100))
    controller = ClientController(
        ClientSessionState(),
        ClientMessageFactory(
            POLICY,
            clock_ms=lambda: 1000,
            request_id_factory=lambda: next(ids),
        ),
        dispatcher,
        localizer or ClientLocalizer(),
        ClientUiConstraints(3, 20, 6),
    )
    return controller, dispatcher


def response(request, message_type, payload):
    return MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": message_type,
            "request_id": request.request_id,
            "timestamp_ms": 1100,
            "payload": payload,
        },
        POLICY,
    )


def accept_login(controller, dispatcher, request, *, rating=1200):
    controller.handle_response(
        response(
            request,
            "command_result",
            {
                "accepted": True,
                "code": "ok",
                "user_id": 7,
                "username": "Dana",
                "rating": rating,
                "auth_token": "auth-token",
                "expires_at_ms": 99999,
            },
        )
    )
    return dispatcher.sent[-1]


def accept_validation(controller, validation, *, rating=1200):
    controller.handle_response(
        response(
            validation,
            "command_result",
            {
                "accepted": True,
                "code": "ok",
                "user_id": 7,
                "username": "Dana",
                "rating": rating,
            },
        )
    )


def authenticate(controller, dispatcher):
    controller.state.fields.update(username="Dana", password="secret7")
    controller.handle_action(UiAction.SUBMIT_LOGIN)
    request = dispatcher.sent[-1]
    validation = accept_login(controller, dispatcher, request)
    accept_validation(controller, validation)


def enter_play_queue(controller, dispatcher):
    controller.tick(1000)
    controller.handle_action(UiAction.PLAY)
    join = dispatcher.sent[-1]
    controller.handle_response(
        response(
            join,
            "play_queue_status",
            {
                "accepted": True,
                "code": "ok",
                "state": "queued",
                "user_id": 7,
                "rating": 1200,
                "enqueued_at_ms": 1000,
                "expires_at_ms": 61000,
            },
        )
    )
    return join


def room_payload(**overrides):
    payload = {
        "accepted": True,
        "code": "ABC234",
        "room_id": 2,
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
    payload.update(overrides)
    return payload


def snapshot_payload(**overrides):
    payload = {
        "board_width": 8,
        "board_height": 8,
        "game_over": False,
        "selected": None,
        "pieces": [
            {
                "row": 6,
                "col": 0,
                "token": "wP",
                "piece_id": 7,
                "state": "idle",
                "rest_remaining_ms": None,
            },
            {
                "row": 6,
                "col": 1,
                "token": "wP",
                "piece_id": 8,
                "state": "idle",
                "rest_remaining_ms": None,
            },
            {
                "row": 1,
                "col": 0,
                "token": "bP",
                "piece_id": 9,
                "state": "idle",
                "rest_remaining_ms": None,
            },
        ],
        "legal_destinations": [],
        "score_by_color": {"w": 0, "b": 0},
        "completed_moves": [],
        "active_motions": [],
        "elapsed_ms": 0,
    }
    payload.update(overrides)
    return payload


def enter_active_play_game(controller, dispatcher):
    authenticate(controller, dispatcher)
    enter_play_queue(controller, dispatcher)
    controller.tick(2000)
    status = dispatcher.sent[-1]
    controller.handle_response(
        response(
            status,
            "play_match_found",
            {
                "accepted": True,
                "code": "ok",
                "state": "match_found",
                "game_id": "game-1",
                "game_token": "game-secret",
                "role": "PLAYER",
                "seat": "FIRST_PLAYER",
                "color": "w",
                "ranked": True,
                "mode": "PLAY",
            },
        )
    )
    resync, lifecycle = dispatcher.sent[-2:]
    assert resync.type == "resync_request"
    assert lifecycle.type == "game_lifecycle_status"
    controller.handle_response(response(resync, "snapshot", snapshot_payload()))
    return lifecycle


def test_login_validates_inline_masks_password_and_stores_session():
    controller, dispatcher = make_controller()
    controller.state.fields.update(username="x", password="short")

    controller.handle_action(UiAction.SUBMIT_LOGIN)
    assert dispatcher.sent == []
    assert "3-20" in controller.state.inline_message

    controller.state.fields.update(username="Dana", password="secret7")
    assert controller.state.display_value("password") == "*******"
    controller.handle_action(UiAction.SUBMIT_LOGIN)
    request = dispatcher.sent[-1]
    assert request.type == "login_request"
    assert controller.state.loading is True

    validation = accept_login(controller, dispatcher, request)
    assert validation.type == "validate_auth_request"
    assert validation.payload["auth_token"] == "auth-token"
    assert controller.state.screen is ClientScreen.LOGIN
    assert controller.state.loading is True
    assert controller.session.authenticated is True

    accept_validation(controller, validation, rating=1216)
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.session.authenticated is True
    assert controller.session.rating == 1216
    assert controller.state.fields["password"] == ""


def test_validation_failure_clears_session_and_returns_to_localized_login():
    controller, dispatcher = make_controller(
        localizer=ClientLocalizer(
            strings={"token_revoked": "Your session is no longer valid."}
        )
    )
    controller.state.fields.update(username="Dana", password="secret7")
    controller.handle_action(UiAction.SUBMIT_LOGIN)
    login = dispatcher.sent[-1]
    validation = accept_login(controller, dispatcher, login)

    controller.handle_response(
        response(
            validation,
            "command_result",
            {"accepted": False, "code": "token_revoked"},
        )
    )

    assert controller.state.screen is ClientScreen.LOGIN
    assert controller.state.inline_message == "Your session is no longer valid."
    assert controller.state.loading is False
    assert controller.session.authenticated is False
    assert "auth-token" not in repr(controller.session)


def test_validation_transport_failure_clears_session_and_returns_to_login():
    controller, dispatcher = make_controller()
    controller.state.fields.update(username="Dana", password="secret7")
    controller.handle_action(UiAction.SUBMIT_LOGIN)
    login = dispatcher.sent[-1]
    validation = accept_login(controller, dispatcher, login)

    controller.handle_transport_failure(validation.request_id)

    assert controller.state.screen is ClientScreen.LOGIN
    assert controller.state.inline_message == "Cannot reach the game server."
    assert controller.session.authenticated is False


def test_registration_validates_fields_and_returns_to_login():
    controller, dispatcher = make_controller()
    controller.handle_action(UiAction.SHOW_REGISTER)
    controller.state.fields.update(
        username="Dana", password="secret7", email="bad", phone="0501234567"
    )
    controller.handle_action(UiAction.SUBMIT_REGISTER)
    assert dispatcher.sent == []
    assert controller.state.inline_message == "Enter a valid email address."

    controller.state.fields.update(email="dana@example.test", phone="12")
    controller.handle_action(UiAction.SUBMIT_REGISTER)
    assert dispatcher.sent == []
    assert controller.state.inline_message == "Enter a valid phone number."

    controller.state.fields["phone"] = "050-123-4567"
    controller.handle_action(UiAction.SUBMIT_REGISTER)
    request = dispatcher.sent[-1]
    assert request.type == "register_request"
    assert request.payload["phone"] == "0501234567"
    controller.handle_response(
        response(
            request,
            "command_result",
            {"accepted": True, "code": "ok", "user_id": 7},
        )
    )
    assert controller.state.screen is ClientScreen.LOGIN
    assert "Account created" in controller.state.inline_message


def test_auth_error_and_transport_failure_clear_password_and_show_inline_error():
    controller, dispatcher = make_controller()
    controller.state.fields.update(username="Dana", password="secret7")
    controller.handle_action(UiAction.SUBMIT_LOGIN)
    request = dispatcher.sent[-1]
    controller.handle_response(
        response(
            request,
            "command_result",
            {"accepted": False, "code": "invalid_credentials"},
        )
    )
    assert controller.state.inline_message == "invalid_credentials"
    assert controller.state.fields["password"] == ""

    controller.state.fields["password"] = "secret7"
    controller.handle_action(UiAction.SUBMIT_LOGIN)
    request = dispatcher.sent[-1]
    controller.handle_transport_failure(request.request_id)
    assert controller.state.inline_message == "Cannot reach the game server."
    assert controller.state.loading is False


def test_play_queue_polls_times_out_and_stores_match_identity():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    join = enter_play_queue(controller, dispatcher)
    assert join.type == "play_queue_join"
    assert join.payload["auth_token"] == "auth-token"
    assert controller.state.screen is ClientScreen.PLAY_QUEUE
    assert controller.state.queue_seconds_elapsed == 0
    assert controller.state.queue_seconds_remaining == 60

    count = len(dispatcher.sent)
    controller.tick(1999)
    assert len(dispatcher.sent) == count
    controller.tick(2000)
    status_request = dispatcher.sent[-1]
    assert status_request.type == "play_queue_status"
    controller.handle_response(
        response(
            status_request,
            "play_match_found",
            {
                "accepted": True,
                "code": "ok",
                "state": "match_found",
                "game_id": "game-1",
                "game_token": "game-secret",
                "role": "PLAYER",
                "seat": "SECOND_PLAYER",
                "color": "b",
                "ranked": True,
                "mode": "PLAY",
            },
        )
    )
    assert controller.state.screen is ClientScreen.MATCH_FOUND
    assert controller.session.game.seat == "SECOND_PLAYER"
    assert controller.session.game.role == "PLAYER"
    assert controller.session.game.color == "b"
    assert "game-secret" not in repr(controller.session)
    assert controller.state.queue_seconds_elapsed is None
    assert controller.state.queue_seconds_remaining is None

    controller.state.screen = ClientScreen.MAIN_MENU
    controller.handle_action(UiAction.PLAY)
    request = dispatcher.sent[-1]
    controller.handle_response(
        response(
            request,
            "matchmaking_timeout",
            {
                "accepted": False,
                "code": "matchmaking_timeout",
                "state": "timed_out",
            },
        )
    )
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.state.inline_message == "matchmaking_timeout"
    assert controller.state.queue_seconds_elapsed is None
    assert controller.state.queue_seconds_remaining is None


def test_play_cancel_returns_to_main_menu():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    enter_play_queue(controller, dispatcher)
    controller.handle_action(UiAction.PLAY_CANCEL)
    request = dispatcher.sent[-1]
    assert request.type == "play_queue_cancel"
    assert request.payload["auth_token"] == "auth-token"
    controller.handle_response(
        response(
            request,
            "play_queue_status",
            {"accepted": True, "code": "ok", "state": "idle", "user_id": 7},
        )
    )
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.state.queue_seconds_elapsed is None
    assert controller.state.queue_seconds_remaining is None


def test_play_status_error_is_localized_on_waiting_screen():
    controller, dispatcher = make_controller(
        localizer=ClientLocalizer(
            strings={"already_in_matchmaking": "You are already waiting."}
        )
    )
    authenticate(controller, dispatcher)
    enter_play_queue(controller, dispatcher)
    controller.tick(2000)
    status_request = dispatcher.sent[-1]

    controller.handle_response(
        response(
            status_request,
            "command_result",
            {"accepted": False, "code": "already_in_matchmaking"},
        )
    )

    assert controller.state.screen is ClientScreen.PLAY_QUEUE
    assert controller.state.inline_message == "You are already waiting."


def test_room_create_stores_player_session_and_polls_status():
    controller, dispatcher = make_controller(
        localizer=ClientLocalizer(strings={"room_closed": "The room closed."})
    )
    authenticate(controller, dispatcher)
    controller.tick(1000)
    controller.handle_action(UiAction.ROOM)
    assert controller.state.screen is ClientScreen.ROOM_ENTRY
    controller.handle_action(UiAction.ROOM_CREATE)
    create = dispatcher.sent[-1]
    assert create.type == "room_create"
    assert create.payload["auth_token"] == "auth-token"

    controller.handle_response(response(create, "room_status", room_payload()))

    assert controller.state.screen is ClientScreen.ROOM_LOBBY
    assert controller.session.room.code == "ABC234"
    assert controller.session.room.seat == "FIRST_PLAYER"
    assert controller.session.room.color == "w"
    assert controller.session.game.game_id == "room-game"
    assert controller.session.game.mode == "ROOM"
    assert "room-token" not in repr(controller.session)

    count = len(dispatcher.sent)
    controller.tick(1999)
    assert len(dispatcher.sent) == count
    controller.tick(2000)
    status = dispatcher.sent[-1]
    assert status.type == "room_status"
    assert status.payload == {"auth_token": "auth-token", "code": "ABC234"}

    refreshed = room_payload(
        status="ACTIVE", player_count=2, gameplay_started=True
    )
    refreshed.pop("game_token")
    controller.handle_response(response(status, "room_status", refreshed))
    assert controller.session.room.status == "ACTIVE"
    assert controller.session.game.game_token == "room-token"

    controller.tick(3000)
    next_status = dispatcher.sent[-1]
    controller.handle_response(
        response(
            next_status,
            "command_result",
            {"accepted": False, "code": "room_closed"},
        )
    )
    assert controller.state.screen is ClientScreen.ROOM_ENTRY
    assert controller.session.room is None
    assert controller.state.inline_message == "The room closed."


def test_room_join_code_validation_manual_status_and_leave():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.ROOM)
    controller.state.fields["room_code"] = "bad"
    controller.handle_action(UiAction.ROOM_JOIN)
    assert controller.state.inline_message == "Enter a 6-character room code."

    controller.state.fields["room_code"] = "abc234"
    controller.handle_action(UiAction.ROOM_JOIN)
    request = dispatcher.sent[-1]
    assert request.type == "room_join"
    assert request.payload["auth_token"] == "auth-token"
    assert request.payload["code"] == "ABC234"
    controller.handle_response(response(request, "room_status", room_payload()))
    assert controller.state.screen is ClientScreen.ROOM_LOBBY
    assert controller.session.room.code == "ABC234"

    controller.handle_action(UiAction.ROOM_REFRESH)
    refresh = dispatcher.sent[-1]
    assert refresh.type == "room_status"
    controller.handle_response(response(refresh, "room_status", room_payload()))
    controller.handle_action(UiAction.ROOM_LEAVE)
    leave = dispatcher.sent[-1]
    assert leave.type == "room_leave"
    assert leave.payload == {"auth_token": "auth-token", "code": "ABC234"}
    controller.handle_response(
        response(leave, "room_status", room_payload(status="CLOSED"))
    )
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.session.room is None
    assert controller.session.game is None
    count = len(dispatcher.sent)
    controller.tick(5000)
    assert len(dispatcher.sent) == count


def test_room_join_error_is_localized_inside_room_entry_screen():
    controller, dispatcher = make_controller(
        localizer=ClientLocalizer(strings={"room_not_found": "Room not found."})
    )
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.ROOM)
    controller.state.fields["room_code"] = "ABC234"
    controller.handle_action(UiAction.ROOM_JOIN)
    join = dispatcher.sent[-1]

    controller.handle_response(
        response(
            join,
            "command_result",
            {"accepted": False, "code": "room_not_found"},
        )
    )

    assert controller.state.screen is ClientScreen.ROOM_ENTRY
    assert controller.state.inline_message == "Room not found."
    assert controller.session.room is None


def test_stale_room_lobby_clears_when_status_reports_room_not_found():
    controller, dispatcher = make_controller(
        localizer=ClientLocalizer(strings={"room_not_found": "Room not found."})
    )
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.ROOM)
    controller.handle_action(UiAction.ROOM_CREATE)
    create = dispatcher.sent[-1]
    controller.handle_response(response(create, "room_status", room_payload()))
    assert controller.state.screen is ClientScreen.ROOM_LOBBY
    assert controller.session.room is not None

    controller.tick(2000)
    status = dispatcher.sent[-1]
    controller.handle_response(
        response(
            status,
            "command_result",
            {"accepted": False, "code": "room_not_found"},
        )
    )

    assert controller.state.screen is ClientScreen.ROOM_ENTRY
    assert controller.session.room is None
    assert controller.state.inline_message == "Room not found."


def test_keyboard_focus_editing_enter_and_loading_gate():
    controller, dispatcher = make_controller()
    controller.handle_key(-1)
    controller.handle_key(9)
    assert controller.state.active_field == "username"
    for character in "Dana":
        controller.handle_key(ord(character))
    controller.handle_key(9)
    for character in "secret7x":
        controller.handle_key(ord(character))
    controller.handle_key(8)
    controller.handle_key(13)
    assert dispatcher.sent[-1].type == "login_request"

    sent = len(dispatcher.sent)
    controller.handle_action(UiAction.SHOW_REGISTER)
    assert len(dispatcher.sent) == sent
    assert controller.state.screen is ClientScreen.LOGIN


def test_room_keyboard_uppercases_alphanumeric_and_cancel_returns_to_menu():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.ROOM)
    controller.activate_field("room_code")
    for character in "ab-c2345":
        controller.handle_key(ord(character))
    assert controller.state.fields["room_code"] == "ABC234"
    sent = len(dispatcher.sent)
    controller.handle_action(UiAction.ROOM_CANCEL)
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert len(dispatcher.sent) == sent


def test_logout_clears_client_session():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.LOGOUT)
    request = dispatcher.sent[-1]
    controller.handle_response(
        response(request, "command_result", {"accepted": True, "code": "ok"})
    )
    assert controller.state.screen is ClientScreen.LOGIN
    assert controller.session.authenticated is False


def test_match_transitions_to_authoritative_board_and_polls_snapshot():
    controller, dispatcher = make_controller()
    lifecycle = enter_active_play_game(controller, dispatcher)

    assert controller.state.screen is ClientScreen.GAME_BOARD
    assert controller.state.game_snapshot.pieces[0].piece_id == 7
    assert controller.state.game_lifecycle_state == "ACTIVE"
    assert lifecycle.payload == {
        "auth_token": "auth-token",
        "game_token": "game-secret",
        "game_id": "game-1",
    }

    controller.handle_response(
        response(
            lifecycle,
            "game_lifecycle_status",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "ACTIVE",
            },
        )
    )
    sent = len(dispatcher.sent)
    controller.tick(2999)
    assert len(dispatcher.sent) == sent
    controller.tick(3000)
    assert {item.type for item in dispatcher.sent[-2:]} == {
        "resync_request",
        "game_lifecycle_status",
    }


def test_board_clicks_dispatch_move_and_jump_then_refresh_immediately():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)

    controller.handle_board_cell(6, 0)
    assert controller.state.game_selected_cell == (6, 0)
    controller.handle_board_cell(4, 0)
    moved = dispatcher.sent[-1]
    assert moved.type == "move_request"
    assert moved.payload["piece_id"] == 7
    assert moved.payload["expected_from"] == {"row": 6, "col": 0}
    assert moved.payload["target"] == {"row": 4, "col": 0}

    controller.handle_response(
        response(
            moved,
            "command_result",
            {
                "accepted": True,
                "code": "ok",
                "sequence": 1,
                "piece_id": 7,
                "snapshot": snapshot_payload(),
            },
        )
    )
    assert controller.state.game_sequence == 1
    assert controller.state.game_snapshot is not None
    assert dispatcher.sent[-1] is moved

    controller.handle_board_cell(6, 0)
    controller.handle_board_cell(6, 0)
    jumped = dispatcher.sent[-1]
    assert jumped.type == "jump_request"
    assert jumped.payload["target"] == jumped.payload["expected_from"]
    controller.handle_response(
        response(
            jumped,
            "command_result",
            {
                "accepted": True,
                "code": "ok",
                "sequence": 2,
                "piece_id": 7,
                "snapshot": snapshot_payload(),
            },
        )
    )
    assert dispatcher.sent[-1] is jumped


def test_active_game_leave_requires_confirm_before_disconnect():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    sent_before = len(dispatcher.sent)

    controller.handle_action(UiAction.GAME_LEAVE)
    assert controller.state.game_leave_confirm_pending is True
    assert controller.state.screen is ClientScreen.GAME_BOARD
    assert len(dispatcher.sent) == sent_before

    controller.handle_action(UiAction.GAME_LEAVE_CANCEL)
    assert controller.state.game_leave_confirm_pending is False

    controller.handle_action(UiAction.GAME_LEAVE)
    controller.handle_action(UiAction.GAME_LEAVE_CONFIRM)
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.session.game is None
    assert dispatcher.sent[-1].type == "game_resign"


def test_ranked_game_finish_refreshes_rating():
    controller, dispatcher = make_controller()
    lifecycle = enter_active_play_game(controller, dispatcher)
    controller.handle_response(
        response(
            lifecycle,
            "game_forfeit",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "ENDED",
                "reason": "forfeit",
                "winner_seat": "SECOND_PLAYER",
            },
        )
    )
    refresh = dispatcher.sent[-1]
    assert refresh.type == "validate_auth_request"
    controller.handle_response(
        response(
            refresh,
            "command_result",
            {
                "accepted": True,
                "code": "ok",
                "user_id": 7,
                "username": "Dana",
                "rating": 1184,
            },
        )
    )
    assert controller.session.rating == 1184
    assert controller.state.screen is ClientScreen.GAME_BOARD


def test_reconnect_countdown_blocks_commands_and_terminal_state_returns_to_menu():
    controller, dispatcher = make_controller()
    lifecycle = enter_active_play_game(controller, dispatcher)
    controller.tick(4000)
    controller.handle_response(
        response(
            lifecycle,
            "game_lifecycle_status",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "PAUSED_FOR_RECONNECT",
                "reconnect_deadline_ms": 23000,
                "remaining_ms": 19000,
            },
        )
    )

    assert controller.state.reconnect_seconds_remaining == 19
    sent = len(dispatcher.sent)
    controller.handle_board_cell(6, 0)
    assert len(dispatcher.sent) == sent
    assert controller.state.inline_message == "game_paused"

    controller.tick(5000)
    terminal_status = dispatcher.sent[-1]
    assert terminal_status.type == "game_lifecycle_status"
    controller.handle_response(
        response(
            terminal_status,
            "game_forfeit",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "ENDED",
                "winner_seat": "FIRST_PLAYER",
                "reason": "forfeit",
            },
        )
    )

    assert controller.state.screen is ClientScreen.GAME_BOARD
    assert controller.state.inline_message == "You won the game."
    assert controller.session.game is not None

    controller.handle_action(UiAction.GAME_LEAVE)
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.session.game is None


def test_active_room_spectator_receives_board_without_player_lifecycle_request():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.ROOM)
    controller.state.fields["room_code"] = "ABC234"
    controller.handle_action(UiAction.ROOM_JOIN)
    joined = dispatcher.sent[-1]
    payload = room_payload(
        status="ACTIVE",
        role="SPECTATOR",
        seat=None,
        color=None,
        game_token="spectator-token",
        player_count=2,
        spectator_count=1,
        gameplay_started=True,
    )
    controller.handle_response(response(joined, "room_status", payload))

    resync = dispatcher.sent[-1]
    assert resync.type == "resync_request"
    assert all(
        item.type != "game_lifecycle_status" for item in dispatcher.sent[-1:]
    )
    controller.handle_response(response(resync, "snapshot", snapshot_payload()))
    assert controller.state.screen is ClientScreen.GAME_BOARD
    assert controller.session.game.seat is None
    sent = len(dispatcher.sent)
    controller.handle_board_cell(6, 0)
    assert len(dispatcher.sent) == sent


def test_unsolicited_state_update_updates_client_snapshot():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)

    controller.handle_push(
        MessageEnvelope.from_mapping(
            {
                "protocol_version": "1.0",
                "type": MessageType.STATE_UPDATE.value,
                "request_id": "push-1",
                "timestamp_ms": 1100,
                "payload": {
                    "game_id": "game-1",
                    "sequence": 1,
                    "snapshot": snapshot_payload(),
                },
            },
            POLICY,
        )
    )

    assert controller.state.game_sequence == 1
    assert controller.state.game_snapshot is not None
    assert controller.state.screen is ClientScreen.GAME_BOARD


def test_sequence_gap_triggers_resync():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    controller.state.game_sequence = 1
    sent = len(dispatcher.sent)

    controller.handle_push(
        MessageEnvelope.from_mapping(
            {
                "protocol_version": "1.0",
                "type": MessageType.STATE_UPDATE.value,
                "request_id": "push-2",
                "timestamp_ms": 1100,
                "payload": {
                    "game_id": "game-1",
                    "sequence": 3,
                    "snapshot": snapshot_payload(),
                },
            },
            POLICY,
        )
    )

    assert len(dispatcher.sent) == sent + 1
    assert dispatcher.sent[-1].type == "resync_request"


def test_network_loss_submits_game_reconnect():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    sent = len(dispatcher.sent)

    assert controller.handle_transport_failure("missing-request", "network_error") is None
    assert len(dispatcher.sent) == sent + 1
    reconnect = dispatcher.sent[-1]
    assert reconnect.type == "game_reconnect"
    assert reconnect.payload["game_id"] == "game-1"


def test_lifecycle_push_forfeit_triggers_rating_refresh():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    sent = len(dispatcher.sent)

    controller.handle_push(
        MessageEnvelope.from_mapping(
            {
                "protocol_version": "1.0",
                "type": MessageType.GAME_FORFEIT.value,
                "request_id": "push-forfeit",
                "timestamp_ms": 1200,
                "payload": {
                    "accepted": True,
                    "code": "ok",
                    "game_id": "game-1",
                    "state": "ENDED",
                    "reason": "forfeit",
                    "winner_seat": "SECOND_PLAYER",
                },
            },
            POLICY,
        )
    )

    assert controller.state.game_lifecycle_state == "ENDED"
    new_requests = dispatcher.sent[sent:]
    assert any(item.type == "validate_auth_request" for item in new_requests)


def test_disconnect_countdown_push_keeps_game_paused():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)

    controller.handle_push(
        MessageEnvelope.from_mapping(
            {
                "protocol_version": "1.0",
                "type": MessageType.DISCONNECT_COUNTDOWN.value,
                "request_id": "push-countdown",
                "timestamp_ms": 1200,
                "payload": {
                    "accepted": True,
                    "code": "ok",
                    "game_id": "game-1",
                    "state": "PAUSED_FOR_RECONNECT",
                    "reconnect_deadline_ms": 25000,
                    "remaining_ms": 15000,
                },
            },
            POLICY,
        )
    )

    assert controller.state.game_lifecycle_state == "PAUSED_FOR_RECONNECT"
    assert controller.state.reconnect_seconds_remaining == 23
    assert all(item.type != "resync_request" for item in dispatcher.sent[-1:])


def test_controller_disconnect_active_game_sends_game_disconnect():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    sent = len(dispatcher.sent)

    controller.disconnect_active_game()

    assert len(dispatcher.sent) == sent + 1
    assert dispatcher.sent[-1].type == "game_disconnect"


def test_stale_client_state_on_move_resubmits_snapshot():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    controller.handle_board_cell(6, 0)
    controller.handle_board_cell(4, 0)
    move = dispatcher.sent[-1]
    sent = len(dispatcher.sent)

    controller.handle_response(
        response(
            move,
            "command_result",
            {"accepted": False, "code": "stale_client_state"},
        )
    )

    assert controller.state.inline_message == "stale_client_state"
    assert len(dispatcher.sent) == sent + 1
    assert dispatcher.sent[-1].type == "resync_request"


def test_invalid_snapshot_response_shows_error_and_reschedules_poll():
    controller, dispatcher = make_controller()
    lifecycle = enter_active_play_game(controller, dispatcher)
    controller.tick(5000)
    snapshot_request = dispatcher.sent[-1]
    assert snapshot_request.type == "resync_request"

    controller.handle_response(
        response(snapshot_request, "snapshot", {"board_width": 8})
    )

    assert controller.state.inline_message == "The server returned an invalid game state."
    controller.tick(6000)
    assert dispatcher.sent[-1].type == "resync_request"


def test_push_without_snapshot_triggers_resync():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    sent = len(dispatcher.sent)

    controller.handle_push(
        MessageEnvelope.from_mapping(
            {
                "protocol_version": "1.0",
                "type": MessageType.STATE_UPDATE.value,
                "request_id": "push-empty",
                "timestamp_ms": 1200,
                "payload": {"game_id": "game-1", "sequence": 2},
            },
            POLICY,
        )
    )

    assert len(dispatcher.sent) == sent + 1
    assert dispatcher.sent[-1].type == "resync_request"


def test_duplicate_sequence_push_is_ignored():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    controller.state.game_sequence = 5
    sent = len(dispatcher.sent)

    controller.handle_push(
        MessageEnvelope.from_mapping(
            {
                "protocol_version": "1.0",
                "type": MessageType.STATE_UPDATE.value,
                "request_id": "push-old",
                "timestamp_ms": 1200,
                "payload": {
                    "game_id": "game-1",
                    "sequence": 4,
                    "snapshot": snapshot_payload(),
                },
            },
            POLICY,
        )
    )

    assert len(dispatcher.sent) == sent
    assert controller.state.game_sequence == 5


def test_tick_schedules_snapshot_and_lifecycle_polls():
    controller, dispatcher = make_controller()
    lifecycle = enter_active_play_game(controller, dispatcher)
    controller.handle_response(
        response(
            lifecycle,
            "game_lifecycle_status",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "ACTIVE",
            },
        )
    )
    sent = len(dispatcher.sent)

    controller.tick(5000)

    new_requests = dispatcher.sent[sent:]
    assert any(item.type == "resync_request" for item in new_requests)
    assert any(item.type == "game_lifecycle_status" for item in new_requests)


def test_board_click_reselects_own_piece():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    controller.handle_board_cell(6, 0)
    assert controller.state.game_selected_piece_id == 7

    controller.handle_board_cell(6, 1)
    assert controller.state.game_selected_piece_id == 8
    assert controller.state.game_selected_cell == (6, 1)


def test_board_click_on_empty_square_clears_selection():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    controller.handle_board_cell(6, 0)
    sent = len(dispatcher.sent)

    controller.handle_board_cell(4, 4)

    assert controller.state.game_selected_piece_id is None
    assert len(dispatcher.sent) == sent + 1
    assert dispatcher.sent[-1].type == "move_request"


def test_terminal_game_over_suppresses_move_error_noise():
    controller, dispatcher = make_controller()
    lifecycle = enter_active_play_game(controller, dispatcher)
    controller.handle_response(
        response(
            lifecycle,
            "game_over",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "ENDED",
                "winner_seat": "FIRST_PLAYER",
            },
        )
    )
    controller.tick(5000)
    move_poll = dispatcher.sent[-1]
    controller.handle_response(
        response(move_poll, "command_result", {"accepted": False, "code": "game_paused"})
    )

    assert controller.state.inline_message == "You won the game."


def test_reconnect_success_resubmits_snapshot():
    controller, dispatcher = make_controller()
    enter_active_play_game(controller, dispatcher)
    sent = len(dispatcher.sent)
    assert controller.handle_transport_failure("missing-request", "network_error") is None
    reconnect = dispatcher.sent[-1]

    controller.handle_response(
        response(
            reconnect,
            "game_lifecycle_status",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "ACTIVE",
            },
        )
    )

    assert len(dispatcher.sent) == sent + 2
    assert dispatcher.sent[-1].type == "resync_request"


def test_spectator_room_payload_bootstraps_snapshot_sequence():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.ROOM)
    controller.state.fields["room_code"] = "ABC234"
    controller.handle_action(UiAction.ROOM_JOIN)
    joined = dispatcher.sent[-1]
    payload = room_payload(
        status="ACTIVE",
        role="SPECTATOR",
        seat=None,
        color=None,
        game_token="spectator-token",
        player_count=2,
        spectator_count=1,
        gameplay_started=True,
        snapshot=snapshot_payload(),
    )
    controller.handle_response(response(joined, "room_status", payload))

    assert controller.state.screen is ClientScreen.GAME_BOARD
    assert controller.state.game_snapshot is not None


def test_leave_after_terminal_game_over_refreshes_rating():
    controller, dispatcher = make_controller()
    lifecycle = enter_active_play_game(controller, dispatcher)
    controller.handle_response(
        response(
            lifecycle,
            "game_over",
            {
                "accepted": True,
                "code": "ok",
                "game_id": "game-1",
                "state": "ENDED",
                "winner_seat": "FIRST_PLAYER",
            },
        )
    )
    refresh = dispatcher.sent[-1]
    assert refresh.type == "validate_auth_request"

    controller.handle_action(UiAction.GAME_LEAVE)
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.session.game is None
