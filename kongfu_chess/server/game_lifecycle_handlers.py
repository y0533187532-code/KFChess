"""Protocol handlers for disconnect, reconnect, and lifecycle status."""

from __future__ import annotations

from ..protocol import MessageType, ProtocolError, ProtocolErrorCode
from .auth_service import AuthError
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_lifecycle_models import GameLifecycleError
from .lifecycle_messages import lifecycle_outgoing
from .routing import OutgoingMessage


class GameLifecycleHandlers:
    _FIELDS = {"auth_token", "game_token", "game_id"}

    def __init__(
        self,
        lifecycle_service,
        *,
        clock_ms,
        seat_adapter=CHESS_SEAT_ADAPTER,
        game_connections=None,
        lifecycle_push=None,
    ):
        self._lifecycle = lifecycle_service
        self._clock_ms = clock_ms
        self._seat_adapter = seat_adapter
        self._game_connections = game_connections
        self._lifecycle_push = lifecycle_push

    def register_routes(self, router) -> None:
        router.register(MessageType.GAME_DISCONNECT.value, self.disconnect)
        router.register(MessageType.GAME_RECONNECT.value, self.reconnect)
        router.register(MessageType.GAME_LIFECYCLE_STATUS.value, self.status)

    async def disconnect(self, context) -> OutgoingMessage:
        payload = self._payload(context)
        return await self._execute(
            context,
            lambda now_ms: self._lifecycle.disconnect(**payload, now_ms=now_ms),
            paused_message=True,
        )

    async def reconnect(self, context) -> OutgoingMessage:
        payload = self._payload(context)
        return await self._execute(
            context,
            lambda now_ms: self._lifecycle.reconnect(**payload, now_ms=now_ms),
        )

    async def status(self, context) -> OutgoingMessage:
        payload = self._payload(context)
        return await self._execute(
            context,
            lambda now_ms: self._lifecycle.status(**payload, now_ms=now_ms),
        )

    async def _execute(self, context, action, *, paused_message: bool = False) -> OutgoingMessage:
        try:
            now_ms = self._clock_ms()
            payload = context.envelope.payload
            self._bind_connection(context.connection_id, payload, now_ms=now_ms)
            view = action(now_ms)
            outgoing = self._message(view, now_ms=now_ms, paused_message=paused_message)
            if self._lifecycle_push is not None:
                await self._lifecycle_push.notify_view(
                    view.game_id,
                    view,
                    now_ms=now_ms,
                    paused_message=paused_message,
                )
            return outgoing
        except (AuthError, GameLifecycleError) as exc:
            return OutgoingMessage(
                MessageType.COMMAND_RESULT.value,
                {"accepted": False, "code": exc.code.value},
            )

    def _bind_connection(self, connection_id, payload, *, now_ms: int) -> None:
        if self._game_connections is None:
            return
        principal, _, _ = self._lifecycle._context.authenticate(
            payload["auth_token"],
            payload["game_token"],
            payload["game_id"],
            now_ms=now_ms,
        )
        self._game_connections.bind(
            connection_id,
            payload["game_id"],
            principal.user_id,
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

    def _message(self, view, *, now_ms: int, paused_message: bool = False) -> OutgoingMessage:
        return lifecycle_outgoing(
            view,
            now_ms=now_ms,
            seat_adapter=self._seat_adapter,
            paused_message=paused_message,
        )
