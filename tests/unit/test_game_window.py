import cv2

from kongfu_chess.engine.types import GameSnapshot
from kongfu_chess.game import Game
from kongfu_chess.graphics.game_window import (
    GAME_WINDOW_NAME,
    MouseClickBuffer,
    SAMPLE_BOARD_SIZE,
    SAMPLE_PAWN_COLUMNS,
    SAMPLE_PAWN_STATES,
    SAMPLE_STEP_FRAMES,
    build_sample_game,
    build_sample_snapshot,
    on_mouse_event,
)


def test_build_sample_snapshot_returns_game_snapshot():
    snapshot = build_sample_snapshot()

    assert isinstance(snapshot, GameSnapshot)


def test_build_sample_snapshot_has_expected_board_size():
    snapshot = build_sample_snapshot()

    assert snapshot.board_width == SAMPLE_BOARD_SIZE
    assert snapshot.board_height == SAMPLE_BOARD_SIZE
    assert snapshot.game_over is False


def test_build_sample_snapshot_contains_expected_pieces():
    snapshot = build_sample_snapshot()

    assert len(snapshot.pieces) == 3
    assert snapshot.pieces[0].token == "wK"
    assert snapshot.pieces[1].token == "bK"
    assert snapshot.pieces[2].token == "wP"


def test_build_sample_snapshot_contains_distinct_piece_ids():
    snapshot = build_sample_snapshot()

    piece_ids = [piece.piece_id for piece in snapshot.pieces]

    assert piece_ids == [1, 2, 3]


def test_build_sample_snapshot_uses_step_to_move_pawn():
    first_snapshot = build_sample_snapshot(0)
    second_snapshot = build_sample_snapshot(1)

    assert first_snapshot.pieces[2].col == SAMPLE_PAWN_COLUMNS[0]
    assert second_snapshot.pieces[2].col == SAMPLE_PAWN_COLUMNS[1]


def test_build_sample_snapshot_uses_step_to_change_pawn_state():
    snapshots = [build_sample_snapshot(index) for index in range(len(SAMPLE_PAWN_STATES))]

    states = [snapshot.pieces[2].state for snapshot in snapshots]

    assert tuple(states) == SAMPLE_PAWN_STATES


def test_slowed_step_keeps_same_snapshot_for_multiple_frames():
    first_snapshot = build_sample_snapshot(0)
    repeated_snapshot = build_sample_snapshot((SAMPLE_STEP_FRAMES - 1) // SAMPLE_STEP_FRAMES)
    next_snapshot = build_sample_snapshot(SAMPLE_STEP_FRAMES // SAMPLE_STEP_FRAMES)

    assert repeated_snapshot.pieces[2].col == first_snapshot.pieces[2].col
    assert next_snapshot.pieces[2].col == SAMPLE_PAWN_COLUMNS[1]


def test_build_sample_game_returns_real_game():
    game = build_sample_game()

    assert isinstance(game, Game)


def test_build_sample_game_snapshot_contains_expected_pieces():
    snapshot = build_sample_game().snapshot()

    assert snapshot.board_width == SAMPLE_BOARD_SIZE
    assert snapshot.board_height == SAMPLE_BOARD_SIZE
    assert sorted(piece.token for piece in snapshot.pieces) == ["bK", "wK", "wP"]


def test_mouse_click_buffer_returns_click_once():
    buffer = MouseClickBuffer()
    buffer.register_click(120, 340)

    assert buffer.pop_click() == (120, 340)
    assert buffer.pop_click() is None


def test_on_mouse_event_registers_left_click():
    buffer = MouseClickBuffer()

    on_mouse_event(cv2.EVENT_LBUTTONDOWN, 12, 34, None, buffer)

    assert buffer.pop_click() == (12, 34)


def test_on_mouse_event_ignores_non_click_event():
    buffer = MouseClickBuffer()

    on_mouse_event(cv2.EVENT_MOUSEMOVE, 12, 34, None, buffer)

    assert buffer.pop_click() is None


def test_window_name_is_not_empty():
    assert GAME_WINDOW_NAME
