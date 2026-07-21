"""GUI-independent coordinator for the OpenCV client screen flows."""

from __future__ import annotations

from ..protocol import MessageEnvelope, MessageType
from .authentication_flow import AuthenticationFlow
from .flow_context import ClientFlowContext
from .matchmaking_flow import MatchmakingFlow
from .room_flow import RoomFlow
from .ui_state import ClientScreen, ClientUiConstraints, ClientUiState, UiAction


class ClientController:
    """Route input and server responses to focused client flows."""

    _FIELD_ORDER = {
        ClientScreen.LOGIN: ("username", "password"),
        ClientScreen.REGISTER: ("username", "password", "email", "phone"),
        ClientScreen.ROOM_ENTRY: ("room_code",),
    }

    def __init__(
        self,
        session,
        messages,
        dispatcher,
        localizer,
        constraints: ClientUiConstraints,
        *,
        status_poll_interval_ms: int = 1000,
    ):
        self._context = ClientFlowContext(
            session, messages, dispatcher, localizer, constraints
        )
        self._authentication = AuthenticationFlow(self._context)
        self._matchmaking = MatchmakingFlow(
            self._context,
            status_poll_interval_ms=status_poll_interval_ms,
        )
        self._rooms = RoomFlow(self._context)
        self._action_flows = (
            self._authentication,
            self._matchmaking,
            self._rooms,
        )

    @property
    def session(self):
        return self._context.session

    @property
    def state(self) -> ClientUiState:
        return self._context.state

    def activate_field(self, field_name: str) -> None:
        if field_name in self._FIELD_ORDER.get(self.state.screen, ()):
            self.state.active_field = field_name

    def handle_key(self, key_code: int) -> None:
        if key_code < 0:
            return
        normalized_code = key_code & 0xFF
        if normalized_code in (10, 13):
            action = {
                ClientScreen.LOGIN: UiAction.SUBMIT_LOGIN,
                ClientScreen.REGISTER: UiAction.SUBMIT_REGISTER,
                ClientScreen.ROOM_ENTRY: UiAction.ROOM_JOIN,
            }.get(self.state.screen)
            if action is not None:
                self.handle_action(action)
            return
        if normalized_code == 9:
            self._focus_next_field()
            return
        field_name = self.state.active_field
        if field_name is None:
            return
        if normalized_code in (8, 127):
            self.state.fields[field_name] = self.state.fields[field_name][:-1]
            return
        if 32 <= normalized_code <= 126:
            self._append_character(field_name, chr(normalized_code))

    def handle_action(self, action: UiAction) -> None:
        if self.state.loading:
            return
        normalized_action = UiAction(action)
        for flow in self._action_flows:
            if flow.handle_action(normalized_action):
                return

    def tick(self, now_ms: int) -> None:
        self.state.now_ms = now_ms
        self._matchmaking.tick(now_ms)

    def handle_response(self, envelope: MessageEnvelope) -> None:
        operation = self._context.complete(envelope.request_id)
        payload = envelope.payload
        if self._matchmaking.handle_timeout(envelope.type):
            return
        if envelope.type == MessageType.ERROR.value or payload.get("accepted") is False:
            error_code = str(payload.get("code", "internal_error"))
            if not self._authentication.handle_failure(operation, error_code):
                self._context.show_error(error_code)
            return
        if self._authentication.handle_success(operation, payload):
            return
        if self._matchmaking.handle_success(envelope.type, payload):
            return
        self._rooms.handle_success(operation, envelope.type, payload)

    def handle_transport_failure(
        self, request_id: str, error_code: str = "network_error"
    ) -> None:
        operation = self._context.complete(request_id)
        if not self._authentication.handle_failure(operation, error_code):
            self._context.show_error(error_code)

    def _append_character(self, field_name: str, character: str) -> None:
        if field_name == "room_code":
            if not character.isalnum():
                return
            character = character.upper()
            maximum = self._context.constraints.room_code_length
        else:
            maximum = 128
        if len(self.state.fields[field_name]) < maximum:
            self.state.fields[field_name] += character

    def _focus_next_field(self) -> None:
        fields = self._FIELD_ORDER.get(self.state.screen, ())
        if not fields:
            return
        if self.state.active_field not in fields:
            self.state.active_field = fields[0]
            return
        index = fields.index(self.state.active_field)
        self.state.active_field = fields[(index + 1) % len(fields)]


__all__ = [
    "ClientController",
    "ClientScreen",
    "ClientUiConstraints",
    "ClientUiState",
    "UiAction",
]
