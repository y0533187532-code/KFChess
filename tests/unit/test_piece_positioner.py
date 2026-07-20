from kongfu_chess.engine.types import MotionSnapshot, PieceSnapshot
from kongfu_chess.graphics.board_view import cell_to_pixels
from kongfu_chess.graphics.piece_positioner import PiecePositioner


def test_find_active_move_for_piece_returns_matching_move():
    positioner = PiecePositioner()
    piece = PieceSnapshot(row=6, col=3, token="wP", piece_id=1)
    matching_move = MotionSnapshot(
        from_pos=(6, 3),
        to_pos=(6, 5),
        total_ms=1000,
        remaining_ms=500,
        order=0,
    )

    active_move = positioner.find_active_move_for_piece(piece, (matching_move,))

    assert active_move == matching_move


def test_find_active_move_for_piece_returns_none_when_no_match():
    positioner = PiecePositioner()
    piece = PieceSnapshot(row=6, col=3, token="wP", piece_id=1)
    other_move = MotionSnapshot(
        from_pos=(1, 3),
        to_pos=(2, 3),
        total_ms=1000,
        remaining_ms=500,
        order=0,
    )

    active_move = positioner.find_active_move_for_piece(piece, (other_move,))

    assert active_move is None


def test_pixel_position_for_piece_without_active_move_uses_cell_position():
    positioner = PiecePositioner()
    piece = PieceSnapshot(row=6, col=3, token="wP", piece_id=1)

    x, y = positioner.pixel_position_for_piece(piece, None)

    assert (x, y) == cell_to_pixels(6, 3)


def test_pixel_position_for_piece_with_active_move_returns_intermediate_position():
    positioner = PiecePositioner()
    piece = PieceSnapshot(row=6, col=3, token="wP", piece_id=1, state="moving")
    active_move = MotionSnapshot(
        from_pos=(6, 3),
        to_pos=(6, 5),
        total_ms=1000,
        remaining_ms=500,
        order=0,
    )

    x, y = positioner.pixel_position_for_piece(piece, active_move)

    assert (x, y) == (400, 600)


def test_pixel_position_for_piece_with_non_positive_total_ms_falls_back_to_cell():
    positioner = PiecePositioner()
    piece = PieceSnapshot(row=6, col=3, token="wP", piece_id=1, state="moving")
    active_move = MotionSnapshot(
        from_pos=(6, 3),
        to_pos=(6, 5),
        total_ms=0,
        remaining_ms=0,
        order=0,
    )

    x, y = positioner.pixel_position_for_piece(piece, active_move)

    assert (x, y) == cell_to_pixels(6, 3)


def test_pixel_position_for_jump_raises_piece_at_midpoint():
    positioner = PiecePositioner()
    piece = PieceSnapshot(row=6, col=3, token="wP", piece_id=1, state="jump")
    active_move = MotionSnapshot(
        from_pos=(6, 3),
        to_pos=(6, 3),
        total_ms=1000,
        remaining_ms=500,
        order=0,
        is_jump=True,
    )

    x, y = positioner.pixel_position_for_piece(piece, active_move)

    assert (x, y) == (300, 550)


def test_pixel_position_for_jump_starts_on_original_cell():
    positioner = PiecePositioner()
    piece = PieceSnapshot(row=6, col=3, token="wP", piece_id=1, state="jump")
    active_move = MotionSnapshot(
        from_pos=(6, 3),
        to_pos=(6, 3),
        total_ms=1000,
        remaining_ms=1000,
        order=0,
        is_jump=True,
    )

    x, y = positioner.pixel_position_for_piece(piece, active_move)

    assert (x, y) == cell_to_pixels(6, 3)
