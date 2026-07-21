"""Shared services used by the client screen flows."""

from __future__ import annotations

from ..protocol import MessageEnvelope
from .ui_state import ClientScreen, ClientUiState


class ClientFlowContext:
    """Own shared UI state and the request lifecycle used by every flow."""

    def __init__(self, session, messages, dispatcher, localizer, constraints):
        self.session = session
        self.messages = messages
        self.constraints = constraints
        self.state = ClientUiState()
        self._dispatcher = dispatcher
        self._localizer = localizer
        self._pending: dict[str, str] = {}
        self._foreground_pending: set[str] = set()

    def submit(
        self,
        envelope: MessageEnvelope,
        operation: str,
        *,
        show_loading: bool = True,
    ) -> None:
        self._pending[envelope.request_id] = operation
        self.state.inline_message = None
        if show_loading:
            self._foreground_pending.add(envelope.request_id)
            self.state.loading = True
        self._dispatcher.submit(envelope)

    def complete(self, request_id: str) -> str | None:
        operation = self._pending.pop(request_id, None)
        self._foreground_pending.discard(request_id)
        self.state.loading = bool(self._foreground_pending)
        return operation

    def show(self, screen: ClientScreen) -> None:
        self.state.screen = screen
        self.state.active_field = None
        self.state.inline_message = None

    def show_error(self, code: str, **values) -> None:
        self.state.inline_message = self._localizer.text(code, **values)

    def show_message(self, code: str, **values) -> None:
        self.state.inline_message = self._localizer.text(code, **values)
