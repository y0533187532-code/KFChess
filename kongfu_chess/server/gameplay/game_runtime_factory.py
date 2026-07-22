"""Create authoritative GameEngine runtimes and bind them to GameSession queues."""

from __future__ import annotations

import asyncio

from ...config import EMPTY_CELL_TOKEN
from ...game import Game
from ...model import GameOverEvent
from ...model.board import Board
from .gameplay_service import GameSessionRegistry, build_game_session
from .tick_scheduler import TickScheduler, needs_advancement


_STANDARD_STARTING_ROWS = (
    ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
    ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
    [EMPTY_CELL_TOKEN] * 8,
    [EMPTY_CELL_TOKEN] * 8,
    [EMPTY_CELL_TOKEN] * 8,
    [EMPTY_CELL_TOKEN] * 8,
    ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
    ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
)


def standard_starting_board() -> Board:
    """Return the default 8x8 opening position for network games."""

    return Board([list(row) for row in _STANDARD_STARTING_ROWS])


class GameRuntimeFactory:
    """Wire a live Game + GameSession into the gameplay registry."""

    def __init__(
        self,
        registry: GameSessionRegistry,
        tick_scheduler: TickScheduler,
        *,
        initial_sequence: int,
        request_cache_size: int,
        lifecycle_service=None,
        push_service=None,
    ):
        self._registry = registry
        self._tick_scheduler = tick_scheduler
        self._initial_sequence = initial_sequence
        self._request_cache_size = request_cache_size
        self.lifecycle_service = lifecycle_service
        self._push_service = push_service
        self._engines: dict[str, object] = {}

    @property
    def registry(self) -> GameSessionRegistry:
        return self._registry

    def bind_lifecycle(self, lifecycle_service) -> None:
        self.lifecycle_service = lifecycle_service

    def engine_for(self, game_id: str):
        return self._engines.get(game_id)

    def start(self, game_id: str):
        existing = self._registry.get(game_id)
        if existing is not None:
            return existing

        game = Game(standard_starting_board())
        if self.lifecycle_service is not None:
            game.subscribe(
                GameOverEvent,
                self.lifecycle_service.subscriber_for(game_id),
            )
        engine = game._engine
        self._engines[game_id] = engine
        on_sequence_changed = None
        if self._push_service is not None:
            push_service = self._push_service

            async def on_sequence_changed(
                changed_game_id, sequence, payload
            ):
                await push_service.notify(changed_game_id, sequence, payload)

        session = build_game_session(
            game_id,
            engine,
            initial_sequence=self._initial_sequence,
            request_cache_size=self._request_cache_size,
            tick_interval_ms=self._tick_scheduler.tick_interval_ms,
            clock_ms=self._tick_scheduler.clock_ms,
            on_sequence_changed=on_sequence_changed,
        )
        session.start()
        self._registry.register(session)
        self._tick_scheduler.start(
            game_id,
            session,
            lambda: needs_advancement(engine),
        )
        return session

    def teardown(self, game_id: str) -> None:
        self._tick_scheduler.stop(game_id)
        self._engines.pop(game_id, None)
        session = self._registry.remove(game_id)
        if session is None:
            return
        self._schedule_close(session)

    def _schedule_close(self, session) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(session.close())
            return
        if loop.is_running():
            loop.create_task(session.close())
            return
        asyncio.run(session.close())
