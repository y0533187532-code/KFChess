"""Atomic arrival resolution: capture removal, placement, king-capture detection."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from ..config import KING_PIECE_TYPE
    from ..model.piece import PIECE_STATE_CAPTURED
except ImportError:
    from config import KING_PIECE_TYPE
    from model.piece import PIECE_STATE_CAPTURED


@dataclass(frozen=True)
class ArrivalResult:
    """Outcome of resolving one motion at its destination cell."""

    captured_piece: object | None
    king_captured: bool


def apply_arrival(
    board,
    from_row,
    from_col,
    to_row,
    to_col,
    moving_color,
    promotion_piece_type=None,
    game_over_piece_type=KING_PIECE_TYPE,
):
    """Remove from source, capture enemy at destination, place mover; return capture info."""
    captured = board.get_cell(to_row, to_col)
    board.move_piece(
        from_row,
        from_col,
        to_row,
        to_col,
        promotion_piece_type=promotion_piece_type,
    )

    marked_captured = None
    if captured is not None:
        marked_captured = captured.with_state(PIECE_STATE_CAPTURED)

    king_captured = (
        captured is not None
        and captured.piece_type == game_over_piece_type
        and captured.color != moving_color
    )
    return ArrivalResult(captured_piece=marked_captured, king_captured=king_captured)
