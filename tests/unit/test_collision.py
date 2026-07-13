"""Unit tests for timed cell-entry collision resolution."""

from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.engine.types import MoveResult
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.rules import RuleEngine


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    engine = GameEngine(board, state, RuleEngine())
    return board, state, engine


def test_later_enemy_captures_earlier_at_same_cell():
    board, _, engine = make_engine([["wR", ".", "bR"]])
    engine.request_move(0, 0, 0, 2)
    engine.request_move(0, 2, 0, 1)
    engine.wait(1000)
    assert board.get_cell(0, 1).token == "bR"
    assert board.get_cell(0, 0) is None


def test_same_color_later_piece_stops_before_conflict():
    board, _, engine = make_engine([["wR", ".", ".", "wQ"]])
    engine.request_move(0, 0, 0, 2)
    engine.request_move(0, 3, 0, 1)
    engine.wait(2000)
    assert board.get_cell(0, 1).token == "wR"
    assert board.get_cell(0, 2).token == "wQ"


def test_overlapping_routes_are_allowed_at_request_time():
    board, _, engine = make_engine([["wR", ".", "bR"]])
    assert engine.request_move(0, 0, 0, 2) == MoveResult(is_accepted=True, reason="ok")
    assert engine.request_move(0, 2, 0, 1) == MoveResult(is_accepted=True, reason="ok")
