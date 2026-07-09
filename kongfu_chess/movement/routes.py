from ..config import PAWN_PIECE_TYPE


# Piece types whose in-flight route is only the destination cell (jumpers /
# single-step movers). Sliders walk every cell from the first step onward.
JUMPING_PIECE_TYPES = frozenset({"K", "N", "P"})


def get_move_route(from_row, from_col, to_row, to_col, piece_type):
    """Return the cells a piece passes through while travelling to ``to``.

    For K/N single-step pawns the route is just the destination. For a
    pawn double-step the route includes the intermediate square and the
    destination. For sliding pieces (R/B/Q) it is every cell from the
    first step through the destination, inclusive.
    """
    if piece_type == PAWN_PIECE_TYPE:
        dr = to_row - from_row
        dc = to_col - from_col
        if abs(dr) == 2 and dc == 0:
            step_row = (dr > 0) - (dr < 0)
            return [(from_row + step_row, from_col), (to_row, to_col)]
        return [(to_row, to_col)]

    if piece_type in JUMPING_PIECE_TYPES:
        return [(to_row, to_col)]

    step_row = (to_row > from_row) - (to_row < from_row)
    step_col = (to_col > from_col) - (to_col < from_col)

    route = []
    row, col = from_row + step_row, from_col + step_col
    while True:
        route.append((row, col))
        if (row, col) == (to_row, to_col):
            break
        row += step_row
        col += step_col
    return route


def is_swap_route(from_a, to_a, color_a, from_b, to_b, color_b):
    """Return True when two enemy moves swap start and end squares."""
    return color_a != color_b and from_a == to_b and to_a == from_b


def is_route_conflict(
    existing_from,
    existing_to,
    existing_route,
    new_from,
    new_to,
    new_route,
    existing_color,
    new_color,
    existing_jump=False,
    new_jump=False,
):
    """Return True if ``new`` cannot be queued while ``existing`` is in-flight."""
    if existing_jump or new_jump:
        return False

    if is_swap_route(existing_from, existing_to, existing_color, new_from, new_to, new_color):
        return False

    if existing_from == new_to:
        return True

    if set(existing_route) & set(new_route):
        return True

    return False
