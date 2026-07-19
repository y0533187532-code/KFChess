import pytest

from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.engine.types import MoveResult, PieceSnapshot
from kongfu_chess.config import DEFAULT_MOVE_DURATION_MS, DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.model.piece_state import PieceState
from kongfu_chess.rules import RuleEngine


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    engine = GameEngine(board, state, RuleEngine())
    return board, state, engine


KING_REST_MS = DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE["K"]
KING_MOVE_MS = DEFAULT_MOVE_DURATION_MS["K"]


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
    assert snapshot.legal_destinations == ((0, 1),)
    assert snapshot.pieces == (
        PieceSnapshot(
            row=0,
            col=0,
            token="wK",
            piece_id=board.get_cell(0, 0).piece_id,
            state=PieceState.IDLE,
            rest_remaining_ms=None,
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
    engine.wait(KING_MOVE_MS - 1)
    assert board.get_cell(0, 0).token == "wK"
    assert engine.has_active_motion() is True


def test_parallel_non_conflicting_moves_both_accepted_while_in_flight():
    """Different pieces may move in parallel; same-piece guard is separate."""
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
    assert board.get_cell(0, 0) is piece

    snapshot = engine.snapshot()
    moving = next(item for item in snapshot.pieces if item.piece_id == piece_id)
    assert moving.state == PieceState.MOVING
    assert moving.rest_remaining_ms is None
    assert moving.row == 0 and moving.col == 0


def test_snapshot_returns_mover_to_idle_after_arrival():
    board, _, engine = make_engine([["wK", "."]])
    piece_id = board.get_cell(0, 0).piece_id
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)

    snapshot = engine.snapshot()
    arrived = next(item for item in snapshot.pieces if item.piece_id == piece_id)
    assert arrived.state == PieceState.RESTING
    assert arrived.rest_remaining_ms == KING_REST_MS
    assert arrived.row == 0 and arrived.col == 1
    assert not hasattr(board.get_cell(0, 1), "state")


def test_snapshot_marks_captured_victim_after_arrival():
    board, state, engine = make_engine([["wR", "bQ"]])
    attacker_id = board.get_cell(0, 0).piece_id
    victim_id = board.get_cell(0, 1).piece_id

    assert next(p for p in engine.snapshot().pieces if p.piece_id == victim_id).state == (
        PieceState.IDLE
    )

    engine.request_move(0, 0, 0, 1)
    mid = engine.snapshot()
    assert next(p for p in mid.pieces if p.piece_id == attacker_id).state == PieceState.MOVING
    assert next(p for p in mid.pieces if p.piece_id == victim_id).state == PieceState.IDLE
    assert board.get_cell(0, 1).token == "bQ"

    engine.wait(1000)
    after = engine.snapshot()
    assert board.get_cell(0, 1).token == "wR"
    assert board.get_cell(0, 0) is None
    assert len(state.captured_pieces) == 1
    captured = next(p for p in after.pieces if p.piece_id == victim_id)
    assert captured.state == PieceState.CAPTURED
    assert captured.rest_remaining_ms is None
    assert captured.row == 0 and captured.col == 1
    attacker = next(p for p in after.pieces if p.piece_id == attacker_id)
    assert attacker.state == PieceState.RESTING
    assert attacker.rest_remaining_ms == KING_REST_MS


def test_request_move_rejects_second_move_while_piece_is_travelling():
    board, _, engine = make_engine([["wK", ".", "."]])
    first = engine.request_move(0, 0, 0, 1)
    second = engine.request_move(0, 0, 1, 0)
    assert first == MoveResult(is_accepted=True, reason="ok")
    assert second == MoveResult(is_accepted=False, reason="piece_in_motion")
    assert len(engine.active_moves) == 1


def test_request_jump_rejects_second_jump_while_airborne():
    board, _, engine = make_engine([["wK"]])
    first = engine.request_jump(0, 0)
    second = engine.request_jump(0, 0)
    assert first == MoveResult(is_accepted=True, reason="ok")
    assert second == MoveResult(is_accepted=False, reason="piece_in_motion")
    assert len(engine.active_moves) == 1


def test_request_move_rejects_while_same_piece_is_jumping():
    board, _, engine = make_engine([["wK", "."]])
    assert engine.request_jump(0, 0) == MoveResult(is_accepted=True, reason="ok")
    result = engine.request_move(0, 0, 0, 1)
    assert result == MoveResult(is_accepted=False, reason="piece_in_motion")
    assert len(engine.active_moves) == 1


def test_request_jump_rejects_while_same_piece_is_travelling():
    board, _, engine = make_engine([["wK", "."]])
    assert engine.request_move(0, 0, 0, 1) == MoveResult(is_accepted=True, reason="ok")
    result = engine.request_jump(0, 0)
    assert result == MoveResult(is_accepted=False, reason="piece_in_motion")
    assert len(engine.active_moves) == 1


def test_piece_may_move_again_after_motion_completes():
    board, _, engine = make_engine([["wK", ".", "."]])
    assert engine.request_move(0, 0, 0, 1) == MoveResult(is_accepted=True, reason="ok")
    engine.wait(1000)
    assert engine.active_moves == []
    result = engine.request_move(0, 1, 0, 2)
    assert result == MoveResult(is_accepted=False, reason="piece_resting")
    engine.wait(KING_REST_MS)
    result = engine.request_move(0, 1, 0, 2)
    assert result == MoveResult(is_accepted=True, reason="ok")
    assert len(engine.active_moves) == 1


def test_request_move_rejects_resting_piece():
    _, _, engine = make_engine([["wK", "."]])
    assert engine.request_move(0, 0, 0, 1) == MoveResult(is_accepted=True, reason="ok")
    engine.wait(1000)
    assert engine.request_move(0, 1, 0, 0) == MoveResult(
        is_accepted=False, reason="piece_resting"
    )


def test_request_jump_rejects_resting_piece():
    _, _, engine = make_engine([["wK", "."]])
    assert engine.request_move(0, 0, 0, 1) == MoveResult(is_accepted=True, reason="ok")
    engine.wait(1000)
    assert engine.request_jump(0, 1) == MoveResult(
        is_accepted=False, reason="piece_resting"
    )


def test_snapshot_returns_idle_after_rest_expires():
    board, _, engine = make_engine([["wK", "."]])
    piece_id = board.get_cell(0, 0).piece_id
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    engine.wait(KING_REST_MS)
    snapshot = engine.snapshot()
    arrived = next(item for item in snapshot.pieces if item.piece_id == piece_id)
    assert arrived.state == PieceState.IDLE
    assert arrived.rest_remaining_ms is None


def test_snapshot_returns_partial_rest_remaining_ms():
    board, _, engine = make_engine([["wK", "."]])
    piece_id = board.get_cell(0, 0).piece_id
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    engine.wait(500)
    snapshot = engine.snapshot()
    arrived = next(item for item in snapshot.pieces if item.piece_id == piece_id)
    assert arrived.state == PieceState.RESTING
    assert arrived.rest_remaining_ms == KING_REST_MS - 500


def test_snapshot_has_no_legal_destinations_when_nothing_selected():
    _, _, engine = make_engine([["wK", "."]])
    assert engine.snapshot().legal_destinations == ()


def test_snapshot_legal_destinations_for_rook_on_open_board():
    board, state, engine = make_engine(
        [
            [".", ".", "."],
            [".", "wR", "."],
            [".", ".", "."],
        ]
    )
    state.select(1, 1)
    assert engine.snapshot().legal_destinations == (
        (0, 1),
        (1, 0),
        (1, 2),
        (2, 1),
    )


def test_snapshot_legal_destinations_excludes_friendly_destination():
    _, state, engine = make_engine(
        [
            [".", "wP", "."],
            [".", "wR", "."],
            [".", ".", "."],
        ]
    )
    state.select(1, 1)
    assert (0, 1) not in engine.snapshot().legal_destinations


def test_snapshot_legal_destinations_includes_enemy_destination():
    _, state, engine = make_engine(
        [
            [".", "bP", "."],
            [".", "wR", "."],
            [".", ".", "."],
        ]
    )
    state.select(1, 1)
    assert (0, 1) in engine.snapshot().legal_destinations


def test_snapshot_legal_destinations_empty_while_selected_piece_is_moving():
    board, state, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    state.select(0, 0)
    assert engine.snapshot().legal_destinations == ()


def test_snapshot_legal_destinations_empty_while_selected_piece_is_resting():
    board, state, engine = make_engine([["wK", "."]])
    engine.request_move(0, 0, 0, 1)
    engine.wait(1000)
    state.select(0, 1)
    assert engine.snapshot().legal_destinations == ()


def test_capture_clears_resting_state_for_captured_piece():
    board = Board([["wR", ".", "bR"]])
    state = GameState(board=board)
    engine = GameEngine(
        board,
        state,
        RuleEngine(),
        move_durations={"R": 1000},
        rest_durations={"R": 2000},
    )
    assert engine.request_move(0, 0, 0, 1) == MoveResult(is_accepted=True, reason="ok")
    engine.wait(1000)
    victim_id = board.get_cell(0, 1).piece_id
    assert engine.arbiter.is_piece_resting(victim_id) is True
    assert engine.request_move(0, 2, 0, 1) == MoveResult(is_accepted=True, reason="ok")
    engine.wait(1000)
    assert board.get_cell(0, 1).token == "bR"
    assert engine.arbiter.is_piece_resting(victim_id) is False
