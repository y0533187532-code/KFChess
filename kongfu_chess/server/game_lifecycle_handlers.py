"""Protocol handlers for disconnect, reconnect, and lifecycle status."""

from __future__ import annotations

from ..protocol import MessageType, ProtocolError, ProtocolErrorCode
from .auth_service import AuthError
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_lifecycle_models import (
    GameLifecycleError,
    GameLifecycleState,
    GameLifecycleView,
)
from .routing import OutgoingMessage


class GameLifecycleHandlers:
    _FIELDS = {"auth_token", "game_token", "game_id"}

    def __init__(self, lifecycle_service, *, clock_ms, seat_adapter=CHESS_SEAT_ADAPTER):
        self._lifecycle = lifecycle_service
        self._clock_ms = clock_ms
        self._seat_adapter = seat_adapter

    def register_routes(self, router) -> None:
        router.register(MessageType.GAME_DISCONNECT.value, self.disconnect)
        router.register(MessageType.GAME_RECONNECT.value, self.reconnect)
        router.register(MessageType.GAME_LIFECYCLE_STATUS.value, self.status)

    def disconnect(self, context) -> OutgoingMessage:
        payload = self._payload(context)
        return self._execute(
            lambda now_ms: self._message(
                self._lifecycle.disconnect(**payload, now_ms=now_ms),
                now_ms=now_ms,
                paused_message=True,
            )
        )

    def reconnect(self, context) -> OutgoingMessage:
        payload = self._payload(context)
        return self._execute(
            lambda now_ms: self._message(
                self._lifecycle.reconnect(**payload, now_ms=now_ms),
                now_ms=now_ms,
            )
        )

    def status(self, context) -> OutgoingMessage:
        payload = self._payload(context)
        return self._execute(
            lambda now_ms: self._message(
                self._lifecycle.status(**payload, now_ms=now_ms),
                now_ms=now_ms,
            )
        )

    def _execute(self, action) -> OutgoingMessage:
        try:
            now_ms = self._clock_ms()
            return action(now_ms)
        except (AuthError, GameLifecycleError) as exc:
            return OutgoingMessage(
                MessageType.COMMAND_RESULT.value,
                {"accepted": False, "code": exc.code.value},
            )

    @classmethod
    def _payload(cls, context):
        payload = context.envelope.payload
        if set(payload) != cls._FIELDS or not all(
            isinstance(payload.get(field), str) and payload[field]
            for field in cls._FIELDS
        ):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "Game lifecycle payload does not match its schema",
            )
        return dict(payload)

    def _message(
        self,
        view: GameLifecycleView,
        *,
        now_ms: int,
        paused_message: bool = False,
    ) -> OutgoingMessage:
        message_type = MessageType.GAME_LIFECYCLE_STATUS
        if view.state is GameLifecycleState.CANCELLED:
            message_type = MessageType.GAME_CANCELLED
        elif view.state is GameLifecycleState.ENDED:
            message_type = (
                MessageType.GAME_FORFEIT
                if view.terminal_reason == "forfeit"
                else MessageType.GAME_OVER
            )
        elif view.state is GameLifecycleState.PAUSED_FOR_RECONNECT and paused_message:
            message_type = MessageType.DISCONNECT_COUNTDOWN

        payload = {
            "accepted": True,
            "code": "ok",
            "game_id": view.game_id,
            "mode": view.mode.value,
            "ranked": view.ranked,
            "state": view.state.value,
            "version": view.version,
            "players": [
                {
                    "user_id": player.user_id,
                    "seat": player.seat.value,
                    "color": self._seat_adapter.protocol_color(player.seat),
                    "connected": player.connected,
                }
                for player in view.players
            ],
        }
        if view.reconnect_deadline_ms is not None:
            payload["reconnect_deadline_ms"] = view.reconnect_deadline_ms
            payload["remaining_ms"] = max(0, view.reconnect_deadline_ms - now_ms)
        if view.winner_seat is not None:
            payload["winner_seat"] = view.winner_seat.value
            payload["winner_color"] = self._seat_adapter.protocol_color(
                view.winner_seat
            )
        if view.terminal_reason is not None:
            payload["reason"] = view.terminal_reason
        return OutgoingMessage(message_type.value, payload)
