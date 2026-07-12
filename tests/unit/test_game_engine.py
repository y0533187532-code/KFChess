import pytest

from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.engine.types import MoveResult, PieceSnapshot
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.model.piece import PIECE_STATE_CAPTURED, PIECE_STATE_IDLE, PIECE_STATE_MOVING
from kongfu_chess.rules import RuleEngine


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    engine = GameEngine(board, state, RuleEngine())
    return board, state, engine


def test_request_move_rejects_game_over_before_validation():
    board, state, engine = make_engine([["wK", "."]])
    state.mark_game_over()
    result = engine.request_move(0, 0, 0, 1)
    assert result == MoveResult(is_accepted=False, reason="game_over")
    assert board.get_cell(0, 0).token == "wK"
    assert engine.active_moves == []


def test_request_move_delegates_legal_move_to_rule_engine():
    board, state, engine = make_engine([["wK", "."]])
    result = engine.request_move(0, 0, 0, 1)
    assert result == MoveResult(is_accepted=True, reason="ok")
    assert len(engine.active_moves) == 1
    assert board.get_cell(0, 0).token == "wK"


def test_request_move_returns_rule_engine_reason_for_illegal_move():
    board, state, engine = make_engine([["wK", ".", "."]])
    result = engine.request_move(0, 0, 0, 2)
    assert result.is_accepted is False
    assert result.reason == "illegal_piece_move"
    assert engine.active_moves == []


def test_invalid_request_does_not_mutate_board():
    board, state, engine = make_engine([["wR", "wP", "."]])
    before = board.render_rows()
    result = engine.request_move(0, 1, 0, 2)
    assert result.is_accepted is False
    assert board.render_rows() == before
    assert engine.active_moves == []


def test_snapshot_exposes_read_only_game_state():
    board, state, engine = make_engine([["wK", "."]])
    state.select(0, 0)
    snapshot = engine.snapshot()
    assert snapshot.board_width == 2
    assert snapshot.board_height == 1
    assert snapshot.game_over is False
    assert snapshot.selected == (0, 0)
    assert snapshot.pieces == (
        PieceSnapshot(
            row=0,
            col=0,
            token="wK",
            piece_id=board.get_cell(0, 0).piece_id,
            state=PIECE_STATE_IDLE,
        ),
    )


def test_request_move_rejects_friendly_destination():
    board, state, engine = make_engine([["wK", "wQ"]])
    result = engine.request_move(0, 0, 0, 1)
    assert result == MoveResult(is_accepted=False, reason="friendly_destination")
    assert engine.active_moves == []


def test_wait_delegates_to_arbiter_without_board_change_mid_flight():
    board, _, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(500)
    assert board.get_cell(0, 0).token == "wK"
    assert engine.has_active_motion() is True


def test_parallel_non_conflicting_moves_both_accepted_while_in_flight():
    """No motion_in_progress guard — second move may start during first."""
    board, _, engine = make_engine([["wK", ".", ".", "bK"]])
    first = engine.request_move(0, 0, 0, 1)
    second = engine.request_move(0, 3, 0, 2)
    assert first == MoveResult(is_accepted=True, reason="ok")
    assert second == MoveResult(is_accepted=True, reason="ok")
    assert len(engine.active_moves) == 2
    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 3).token == "bK"


def test_snapshot_derives_moving_state_from_active_motions_without_mutating_board():
    board, _, engine = make_engine([["wK", "."]])
    piece = board.get_cell(0, 0)
    piece_id = piece.piece_id
    engine.request_move(0, 0, 0, 1)

    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 0).state == PIECE_STATE_IDLE

    snapshot = engine.snapshot()
    moving = next(item for item in snapshot.pieces if item.piece_id == piece_id)
    assert moving.state == PIECE_STATE_MOVING
    assert moving.row == 0 and moving.col == 0


def test_snapshot_returns_mover_to_idle_after_arrival():
    board, _, engine = make_engine([["wK", "."]])
    piece_id = board.get_cell(0, 0).piece_id
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)

    snapshot = engine.snapshot()
    arrived = next(item for item in snapshot.pieces if item.piece_id == piece_id)
    assert arrived.state == PIECE_STATE_IDLE
    assert arrived.row == 0 and arrived.col == 1
    assert board.get_cell(0, 1).state == PIECE_STATE_IDLE


def test_snapshot_marks_captured_victim_after_arrival():
    board, state, engine = make_engine([["wR", "bQ"]])
    attacker_id = board.get_cell(0, 0).piece_id
    victim_id = board.get_cell(0, 1).piece_id

    assert next(p for p in engine.snapshot().pieces if p.piece_id == victim_id).state == (
        PIECE_STATE_IDLE
    )

    engine.request_move(0, 0, 0, 1)
    mid = engine.snapshot()
    assert next(p for p in mid.pieces if p.piece_id == attacker_id).state == PIECE_STATE_MOVING
    assert next(p for p in mid.pieces if p.piece_id == victim_id).state == PIECE_STATE_IDLE
    assert board.get_cell(0, 1).token == "bQ"

    engine.wait(1000)
    after = engine.snapshot()
    assert board.get_cell(0, 1).token == "wR"
    assert board.get_cell(0, 0) is None
    assert len(state.captured_pieces) == 1
    captured = next(p for p in after.pieces if p.piece_id == victim_id)
    assert captured.state == PIECE_STATE_CAPTURED
    assert captured.row == 0 and captured.col == 1
    assert next(p for p in after.pieces if p.piece_id == attacker_id).state == PIECE_STATE_IDLE
