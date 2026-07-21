"""Broadcast lifecycle messages to every bound socket in an active game."""

from __future__ import annotations

from .chess_compatibility import CHESS_SEAT_ADAPTER
from .lifecycle_messages import lifecycle_outgoing


class LifecyclePushService:
    def __init__(self, gateway, game_connections, *, clock_ms, seat_adapter=CHESS_SEAT_ADAPTER):
        self._gateway = gateway
        self._game_connections = game_connections
        self._clock_ms = clock_ms
        self._seat_adapter = seat_adapter

    async def notify_view(
        self,
        game_id: str,
        view,
        *,
        now_ms: int | None = None,
        paused_message: bool = False,
        exclude=(),
    ) -> None:
        resolved_now_ms = self._clock_ms() if now_ms is None else now_ms
        outgoing = lifecycle_outgoing(
            view,
            now_ms=resolved_now_ms,
            seat_adapter=self._seat_adapter,
            paused_message=paused_message,
        )
        await self._gateway.broadcast(game_id, outgoing, exclude=exclude)

    async def notify_views(
        self,
        views,
        *,
        now_ms: int | None = None,
        paused_message: bool = False,
    ) -> None:
        resolved_now_ms = self._clock_ms() if now_ms is None else now_ms
        for view in views:
            await self.notify_view(
                view.game_id,
                view,
                now_ms=resolved_now_ms,
                paused_message=paused_message,
            )
