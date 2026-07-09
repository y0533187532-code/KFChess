try:
    from ..config import (
        DEFAULT_PAWN_FORWARD_BY_COLOR,
        DEFAULT_PAWN_START_ROW_BY_COLOR,
    )
except ImportError:
    from config import (
        DEFAULT_PAWN_FORWARD_BY_COLOR,
        DEFAULT_PAWN_START_ROW_BY_COLOR,
    )


def pawn_start_row(color, num_rows, start_row_by_color=DEFAULT_PAWN_START_ROW_BY_COLOR):
    placement = start_row_by_color[color]
    if placement == "bottom":
        return num_rows - 1
    return 0


def is_promotion_row(row, num_rows):
    """Return True if row is a promotion row (consumed by Game's promotion policy, not MovementRules)."""
    return row == 0 or row == num_rows - 1


def is_pawn_move(
    dr,
    dc,
    color,
    target_piece,
    board=None,
    from_row=None,
    from_col=None,
    to_col=None,
    forward_by_color=DEFAULT_PAWN_FORWARD_BY_COLOR,
    start_row_by_color=DEFAULT_PAWN_START_ROW_BY_COLOR,
):
    """Return True if a pawn of ``color`` can move by (dr, dc) to a cell
    occupied by ``target_piece`` (a Piece or None for an empty cell).

    For a double-step forward from the start row, ``board``, ``from_row``,
    ``from_col``, and ``to_col`` are required to verify the intermediate
    cell is empty.
    """
    forward = forward_by_color[color]
    if dc == 0 and dr == forward:
        return target_piece is None
    if (
        dc == 0
        and dr == 2 * forward
        and board is not None
        and from_row is not None
        and from_col is not None
        and to_col is not None
    ):
        if from_row != pawn_start_row(color, board.num_rows, start_row_by_color):
            return False
        if target_piece is not None:
            return False
        inter_row = from_row + forward
        return board.get_cell(inter_row, to_col) is None
    if abs(dc) == 1 and dr == forward:
        return target_piece is not None and target_piece.color != color
    return False
