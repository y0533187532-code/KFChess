import pytest

from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.engine.types import MoveResult
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.model.piece import PIECE_STATE_CAPTURED
from kongfu_chess.realtime.arrival_resolver import apply_arrival
from kongfu_chess.rules import RuleEngine


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    engine = GameEngine(board, state, RuleEngine())
    return board, state, engine


def test_apply_arrival_removes_captured_enemy_from_board():
    board = Board([["wR", "bQ"]])
    result = apply_arrival(board, 0, 0, 0, 1, "w")
    assert board.get_cell(0, 1).token == "wR"
    assert board.get_cell(0, 0) is None
    assert result.captured_piece.token == "bQ"
    assert result.captured_piece.state == PIECE_STATE_CAPTURED
    assert result.king_captured is False


def test_apply_arrival_detects_king_capture():
    board = Board([["wR", "bK"]])
    result = apply_arrival(board, 0, 0, 0, 1, "w")
    assert result.king_captured is True
    assert result.captured_piece.token == "bK"


def test_non_king_capture_on_arrival_does_not_end_game():
    board, state, engine = make_engine([["wR", "bQ"]])
    engine.request_move(0, 0, 0, 1)
    assert state.is_game_over is False
    engine.wait(1000)
    assert board.get_cell(0, 1).token == "wR"
    assert state.is_game_over is False
    assert state.score_by_color == {"w": 9, "b": 0}


def test_king_capture_on_arrival_sets_game_over():
    board, state, engine = make_engine([["wR", "bK"]])
    engine.request_move(0, 0, 0, 1)
    assert state.is_game_over is False
    engine.wait(1000)
    assert board.get_cell(0, 1).token == "wR"
    assert state.is_game_over is True
    assert state.score_by_color == {"w": 0, "b": 0}


def test_capture_not_applied_before_arrival():
    board, state, engine = make_engine([["wR", "bQ"]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(500)
    assert board.get_cell(0, 0).token == "wR"
    assert board.get_cell(0, 1).token == "bQ"
    assert state.is_game_over is False


def test_request_move_rejected_after_king_capture_game_over():
    board, state, engine = make_engine([["wR", "bK"]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    result = engine.request_move(0, 1, 0, 0)
    assert result == MoveResult(is_accepted=False, reason="game_over")


def test_rule_engine_unaware_of_game_over():
    board, state, engine = make_engine([["wR", "bK"]])
    state.mark_game_over()
    validation = engine.rule_engine.validate_move(board, 0, 0, 0, 1)
    assert validation.is_valid is True


def test_white_capture_of_black_pawn_adds_one_point():
    board, state, engine = make_engine([["wR", "bP"]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    assert state.score_by_color == {"w": 1, "b": 0}


def test_black_capture_of_white_queen_adds_nine_points():
    board, state, engine = make_engine([["bR", "wQ"]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    assert state.score_by_color == {"w": 0, "b": 9}


def test_snapshot_exposes_score_by_color():
    board, state, engine = make_engine([["wR", "bP"]])
    assert engine.snapshot().score_by_color == {"w": 0, "b": 0}
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    assert engine.snapshot().score_by_color == {"w": 1, "b": 0}
