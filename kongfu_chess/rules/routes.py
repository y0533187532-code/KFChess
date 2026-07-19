try:
    from ..config import KING_PIECE_TYPE, KNIGHT_PIECE_TYPE, PAWN_PIECE_TYPE
except ImportError:
    from config import KING_PIECE_TYPE, KNIGHT_PIECE_TYPE, PAWN_PIECE_TYPE


JUMPING_PIECE_TYPES = frozenset(
    {KING_PIECE_TYPE, KNIGHT_PIECE_TYPE, PAWN_PIECE_TYPE}
)


def get_move_route(from_row, from_col, to_row, to_col, piece_type):
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
    return color_a != color_b and from_a == to_b and to_a == from_b


def _is_horizontal_route(route, from_cell, to_cell):
    return bool(route) and from_cell[0] == to_cell[0]


def _is_vertical_route(route, from_cell, to_cell):
    return bool(route) and from_cell[1] == to_cell[1]


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
    if existing_jump or new_jump:
        return False

    if is_swap_route(existing_from, existing_to, existing_color, new_from, new_to, new_color):
        return False

    if existing_from == new_to:
        return True

    if set(existing_route) & set(new_route):
        return True

    if existing_color != new_color:
        existing_cols = {col for _, col in existing_route}
        new_cols = {col for _, col in new_route}
        existing_rows = {row for row, _ in existing_route}
        new_rows = {row for row, _ in new_route}
        shared_cols = existing_cols & new_cols
        shared_rows = existing_rows & new_rows
        if (
            shared_cols
            and _is_horizontal_route(existing_route, existing_from, existing_to)
            and _is_horizontal_route(new_route, new_from, new_to)
            and not shared_rows
        ):
            return True
        if (
            shared_rows
            and _is_vertical_route(existing_route, existing_from, existing_to)
            and _is_vertical_route(new_route, new_from, new_to)
            and not shared_cols
        ):
            return True

    return False
