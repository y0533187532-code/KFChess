"""Hybrid authoritative tick scheduling for active GameSession queues."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from types import MappingProxyType

from .game_session import GameSession, SessionCommand, SessionCommandType


def needs_advancement(engine) -> bool:
    """Return True when simulated time should continue advancing."""

    if engine.state.is_game_over:
        return False
    return engine.has_active_motion() or bool(engine.arbiter.active_rests)


class TickScheduler:
    """Submit TICK commands to each active game through its FIFO worker."""

    def __init__(
        self,
        *,
        tick_interval_ms: int,
        clock_ms: Callable[[], int] | None = None,
    ):
        if tick_interval_ms < 1:
            raise ValueError("tick_interval_ms must be positive")
        self.tick_interval_ms = tick_interval_ms
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._tasks: dict[str, asyncio.Task] = {}
        self._needs_advancement: dict[str, Callable[[], bool]] = {}

    def start(
        self,
        game_id: str,
        session: GameSession,
        needs_advancement_fn: Callable[[], bool],
    ) -> None:
        if game_id in self._tasks:
            return
        self._needs_advancement[game_id] = needs_advancement_fn
        self._tasks[game_id] = asyncio.create_task(
            self._run(game_id, session),
            name=f"tick-scheduler:{game_id}",
        )

    def stop(self, game_id: str) -> None:
        task = self._tasks.pop(game_id, None)
        self._needs_advancement.pop(game_id, None)
        if task is None:
            return
        task.cancel()

    async def _run(self, game_id: str, session: GameSession) -> None:
        interval_seconds = self.tick_interval_ms / 1000
        try:
            while True:
                await asyncio.sleep(interval_seconds)
                if session.is_paused:
                    continue
                needs_fn = self._needs_advancement.get(game_id)
                if needs_fn is None or not needs_fn():
                    continue
                await session.submit(
                    SessionCommand(
                        kind=SessionCommandType.TICK.value,
                        request_id=None,
                        payload=MappingProxyType(
                            {"interval_ms": self.tick_interval_ms}
                        ),
                    )
                )
        except asyncio.CancelledError:
            raise
