from kongfu_chess.client import (
    ClientController,
    ClientLocalizer,
    ClientMessageFactory,
    ClientScreen,
    ClientSessionState,
    ClientUiConstraints,
    UiAction,
)
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


class Dispatcher:
    def __init__(self):
        self.sent = []

    def submit(self, envelope):
        self.sent.append(envelope)


def make_controller(*, localizer=None):
    dispatcher = Dispatcher()
    ids = iter(f"request-{index}" for index in range(30))
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


def test_play_queue_polls_cancels_times_out_and_stores_match_identity():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
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
    assert controller.state.screen is ClientScreen.PLAY_QUEUE
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
                "color": "b",
                "ranked": True,
                "mode": "PLAY",
            },
        )
    )
    assert controller.state.screen is ClientScreen.MATCH_FOUND
    assert controller.session.game.seat == "SECOND_PLAYER"

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


def test_play_cancel_returns_to_main_menu():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    controller.state.screen = ClientScreen.PLAY_QUEUE
    controller.handle_action(UiAction.PLAY_CANCEL)
    request = dispatcher.sent[-1]
    controller.handle_response(
        response(
            request,
            "play_queue_status",
            {"accepted": True, "code": "ok", "state": "idle", "user_id": 7},
        )
    )
    assert controller.state.screen is ClientScreen.MAIN_MENU


def test_room_create_refresh_leave_and_join_code_validation():
    controller, dispatcher = make_controller()
    authenticate(controller, dispatcher)
    controller.handle_action(UiAction.ROOM)
    assert controller.state.screen is ClientScreen.ROOM_ENTRY
    controller.state.fields["room_code"] = "bad"
    controller.handle_action(UiAction.ROOM_JOIN)
    assert controller.state.inline_message == "Enter a 6-character room code."

    controller.state.fields["room_code"] = "abc234"
    controller.handle_action(UiAction.ROOM_JOIN)
    request = dispatcher.sent[-1]
    assert request.payload["code"] == "ABC234"
    room_payload = {
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
    controller.handle_response(response(request, "room_status", room_payload))
    assert controller.state.screen is ClientScreen.ROOM_LOBBY
    assert controller.session.room.code == "ABC234"

    controller.handle_action(UiAction.ROOM_REFRESH)
    refresh = dispatcher.sent[-1]
    assert refresh.type == "room_status"
    controller.handle_response(response(refresh, "room_status", room_payload))
    controller.handle_action(UiAction.ROOM_LEAVE)
    leave = dispatcher.sent[-1]
    controller.handle_response(response(leave, "room_status", room_payload))
    assert controller.state.screen is ClientScreen.MAIN_MENU
    assert controller.session.room is None


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
    controller.handle_action(UiAction.ROOM_CANCEL)
    assert controller.state.screen is ClientScreen.MAIN_MENU


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
