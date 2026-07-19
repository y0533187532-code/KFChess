import pytest

from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.config import (
    DEFAULT_MOVE_DURATION_MS,
    DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE,
)
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.rules import RuleEngine


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    engine = GameEngine(board, state, RuleEngine())
    return board, state, engine


KING_MOVE_MS = DEFAULT_MOVE_DURATION_MS["K"]
KING_REST_MS = DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE["K"]
ROOK_MOVE_MS = DEFAULT_MOVE_DURATION_MS["R"]
BISHOP_MOVE_MS = DEFAULT_MOVE_DURATION_MS["B"]


def test_has_active_motion_false_when_idle():
    _, _, engine = make_engine([["wK", "."]])
    assert engine.has_active_motion() is False


def test_schedule_travel_sets_active_motion():
    board, _, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    assert engine.has_active_motion() is True
    assert board.get_cell(0, 0).token == "wK"


def test_piece_does_not_arrive_before_duration_elapses():
    board, _, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(KING_MOVE_MS - 1)
    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 1) is None


def test_piece_arrives_after_full_duration():
    board, _, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(KING_MOVE_MS)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 1).token == "wK"


def test_partial_waits_accumulate_to_arrival():
    board, _, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(KING_MOVE_MS // 4)
    engine.wait(KING_MOVE_MS // 4)
    assert board.get_cell(0, 0).token == "wK"
    engine.wait(KING_MOVE_MS // 2)
    assert board.get_cell(0, 1).token == "wK"


def test_two_cell_move_requires_two_seconds():
    board, _, engine = make_engine([["wR", ".", "."]])
    engine.request_move(0, 0, 0, 2)
    engine.wait(ROOK_MOVE_MS)
    assert board.get_cell(0, 0).token == "wR"
    assert board.get_cell(0, 2) is None
    engine.wait(ROOK_MOVE_MS)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 2).token == "wR"


def test_bishop_three_diagonal_squares_requires_three_seconds():
    """Design guide §10: diagonal duration uses cell steps, not pixel distance."""
    board, _, engine = make_engine(
        [
            ["wB", ".", ".", "."],
            [".", ".", ".", "."],
            [".", ".", ".", "."],
            [".", ".", ".", "."],
        ]
    )
    engine.request_move(0, 0, 3, 3)
    engine.wait(BISHOP_MOVE_MS * 2)
    assert board.get_cell(0, 0).token == "wB"
    assert board.get_cell(3, 3) is None
    engine.wait(BISHOP_MOVE_MS)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(3, 3).token == "wB"


def test_arbiter_exposes_active_moves_through_engine():
    _, _, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    assert len(engine.arbiter.active_moves) == 1
    assert engine.has_active_motion() is True


def test_negative_wait_does_not_extend_remaining_time():
    board, _, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(-500)
    assert engine.active_moves[0]["remaining"] == KING_MOVE_MS
    engine.wait(KING_MOVE_MS)
    assert board.get_cell(0, 1).token == "wK"


def test_rest_timer_counts_down_after_arrival():
    _, _, engine = make_engine([["wK", "."]])
    piece_id = engine.board.get_cell(0, 0).piece_id
    engine.request_move(0, 0, 0, 1)
    engine.wait(KING_MOVE_MS)
    assert engine.arbiter.active_rests[piece_id] == KING_REST_MS
    engine.wait(300)
    assert engine.arbiter.active_rests[piece_id] == KING_REST_MS - 300
    engine.wait(KING_REST_MS - 300)
    assert piece_id not in engine.arbiter.active_rests
