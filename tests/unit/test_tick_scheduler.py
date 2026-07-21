import asyncio
from types import MappingProxyType, SimpleNamespace

import pytest

from kongfu_chess.config import DEFAULT_MOVE_DURATION_MS, DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE
from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.rules import RuleEngine
from kongfu_chess.server import (
    SessionCommand,
    SessionCommandType,
    TickScheduler,
    build_game_session,
    needs_advancement,
)


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    return GameEngine(board, state, RuleEngine())


KING_MOVE_MS = DEFAULT_MOVE_DURATION_MS["K"]
KING_REST_MS = DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE["K"]


def test_needs_advancement_reflects_motion_rest_and_game_over():
    engine = make_engine([["wK", "."]])
    assert needs_advancement(engine) is False

    engine.request_move(0, 0, 0, 1)
    assert needs_advancement(engine) is True

    engine.wait(KING_MOVE_MS - 1)
    assert needs_advancement(engine) is True

    engine.wait(1)
    assert needs_advancement(engine) is True

    engine.wait(KING_REST_MS)
    assert needs_advancement(engine) is False

    engine.state.mark_game_over()
    assert needs_advancement(engine) is False


def test_tick_scheduler_submits_tick_while_motion_is_active():
    async def scenario():
        engine = make_engine([["wK", "."]])
        engine.request_move(0, 0, 0, 1)
        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
            tick_interval_ms=10,
        )
        session.start()
        scheduler = TickScheduler(tick_interval_ms=10)
        scheduler.start("game-1", session, lambda: needs_advancement(engine))

        await asyncio.sleep(1.8)
        scheduler.stop("game-1")
        await asyncio.sleep(0)

        assert session.sequence > 0
        assert engine.snapshot().pieces[0].col == 1

    asyncio.run(scenario())


def test_tick_scheduler_does_not_submit_when_idle():
    async def scenario():
        engine = make_engine([["wK", "."]])
        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
            tick_interval_ms=10,
        )
        session.start()
        scheduler = TickScheduler(tick_interval_ms=10)
        scheduler.start("game-1", session, lambda: needs_advancement(engine))

        await asyncio.sleep(0.05)
        scheduler.stop("game-1")
        await asyncio.sleep(0)

        assert session.sequence == 0

    asyncio.run(scenario())


def test_tick_skipped_when_session_is_paused():
    async def scenario():
        engine = make_engine([["wK", "."]])
        engine.request_move(0, 0, 0, 1)
        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
            tick_interval_ms=10,
        )
        session.start()
        session.pause()

        result = await session.submit(
            SessionCommand(
                kind=SessionCommandType.TICK.value,
                request_id=None,
                payload=MappingProxyType({"interval_ms": 10}),
            )
        )

        assert result.accepted is False
        assert result.code == "game_paused"
        assert engine.snapshot().pieces[0].col == 0

    asyncio.run(scenario())


def test_tick_scheduler_rejects_non_positive_interval():
    with pytest.raises(ValueError, match="tick_interval_ms"):
        TickScheduler(tick_interval_ms=0)
