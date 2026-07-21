"""Ranked Play queue behavior for the client controller."""

from __future__ import annotations

from ..protocol import MessageType
from .ui_state import ClientScreen, UiAction


class MatchmakingFlow:
    _ACTIONS = {UiAction.PLAY, UiAction.PLAY_CANCEL}

    def __init__(self, context, *, status_poll_interval_ms: int):
        self._context = context
        self._status_poll_interval_ms = status_poll_interval_ms
        self._next_status_poll_ms: int | None = None

    def handle_action(self, action: UiAction) -> bool:
        if action not in self._ACTIONS:
            return False
        auth_token = self._context.session.require_auth_token()
        if action is UiAction.PLAY:
            envelope = self._context.messages.play_join(auth_token)
            operation = "play_join"
        else:
            envelope = self._context.messages.play_cancel(auth_token)
            operation = "play_cancel"
        self._context.submit(envelope, operation)
        return True

    def tick(self, now_ms: int) -> None:
        state = self._context.state
        if (
            state.screen is ClientScreen.PLAY_QUEUE
            and not state.loading
            and self._next_status_poll_ms is not None
            and now_ms >= self._next_status_poll_ms
        ):
            self._context.submit(
                self._context.messages.play_status(
                    self._context.session.require_auth_token()
                ),
                "play_status",
            )
            self._next_status_poll_ms = now_ms + self._status_poll_interval_ms

    def handle_timeout(self, message_type: str) -> bool:
        if message_type != MessageType.MATCHMAKING_TIMEOUT.value:
            return False
        self._stop_polling()
        self._context.show(ClientScreen.MAIN_MENU)
        self._context.show_error("matchmaking_timeout")
        return True

    def handle_success(self, message_type: str, payload) -> bool:
        if message_type == MessageType.PLAY_MATCH_FOUND.value:
            self._context.session.store_play_match(payload)
            self._stop_polling()
            self._context.show(ClientScreen.MATCH_FOUND)
            return True
        if message_type != MessageType.PLAY_QUEUE_STATUS.value:
            return False
        self._handle_queue_status(payload)
        return True

    def _handle_queue_status(self, payload) -> None:
        queue_state = str(payload.get("state", "idle"))
        if queue_state == "queued":
            self._context.state.screen = ClientScreen.PLAY_QUEUE
            self._context.state.queue_expires_at_ms = int(payload["expires_at_ms"])
            self._next_status_poll_ms = (
                self._context.state.now_ms + self._status_poll_interval_ms
            )
        elif queue_state == "match_found":
            self._context.session.store_play_match(payload)
            self._context.show(ClientScreen.MATCH_FOUND)
        else:
            self._stop_polling()
            self._context.show(ClientScreen.MAIN_MENU)

    def _stop_polling(self) -> None:
        self._context.state.queue_expires_at_ms = None
        self._next_status_poll_ms = None
