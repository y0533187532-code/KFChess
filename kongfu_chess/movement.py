"""Shape-only movement legality for piece types.

Each function here answers one question only: "is (dr, dc) a legal shape
for this piece type?" - no board access, no piece objects, no side
effects. That keeps them trivially unit-testable and reusable regardless
of how the board itself is represented internally.

``MovementRules`` is the registry that ties a piece_type letter to its
shape-check function. It is a *class*, not a bare module-level dict, so a
future "design your own game" feature can build its own registry (or
``.register()`` new piece types onto a copy of the default one) without
ever touching this module - nothing here assumes only these five piece
types will ever exist.
"""

from .config import PAWN_PIECE_TYPE


def is_king_move(dr, dc):
    return max(abs(dr), abs(dc)) == 1


def is_rook_move(dr, dc):
    return (dr == 0) != (dc == 0)


def is_bishop_move(dr, dc):
    return dr != 0 and abs(dr) == abs(dc)


def is_knight_move(dr, dc):
    return {abs(dr), abs(dc)} == {1, 2}


def is_queen_move(dr, dc):
    return is_rook_move(dr, dc) or is_bishop_move(dr, dc)


def pawn_start_row(color, num_rows):
    return num_rows - 1 if color == "w" else 0


def is_promotion_row(row, num_rows):
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
):
    """Return True if a pawn of ``color`` can move by (dr, dc) to a cell
    occupied by ``target_piece`` (a Piece or None for an empty cell).

    For a double-step forward from the start row, ``board``, ``from_row``,
    ``from_col``, and ``to_col`` are required to verify the intermediate
    cell is empty.
    """
    forward = -1 if color == "w" else 1
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
        if from_row != pawn_start_row(color, board.num_rows):
            return False
        if target_piece is not None:
            return False
        inter_row = from_row + forward
        return board.get_cell(inter_row, to_col) is None
    if abs(dc) == 1 and dr == forward:
        return target_piece is not None and target_piece.color != color
    return False


# Default rule-set for the five non-pawn piece types.
# Pawn is absent here because its rule needs context (color + target_piece)
# that the plain (dr, dc) signature cannot carry. MovementRules.is_legal
# handles pawn transparently via is_pawn_move, so callers never need to
# know which piece types are "special".
DEFAULT_MOVEMENT_RULES = {
    "K": is_king_move,
    "R": is_rook_move,
    "B": is_bishop_move,
    "N": is_knight_move,
    "Q": is_queen_move,
}

# Piece types that "slide" and therefore need every cell strictly between
# source and destination to be empty. Knight is deliberately absent - it
# jumps over blockers by definition, and king only ever moves one cell (no
# intermediate cell exists to check).
DEFAULT_SLIDING_PIECE_TYPES = frozenset({"R", "B", "Q"})


def is_path_clear(board, from_row, from_col, to_row, to_col):
    """Return True if every cell strictly between the two given cells is
    empty on ``board``.

    Only meaningful for a straight line or diagonal (i.e. a move already
    confirmed legal by MovementRules.is_legal for a sliding piece type) -
    it walks one step at a time toward the destination using the board's
    own public ``get_cell``, never touching board internals directly.
    """
    step_row = (to_row > from_row) - (to_row < from_row)
    step_col = (to_col > from_col) - (to_col < from_col)

    row, col = from_row + step_row, from_col + step_col
    while (row, col) != (to_row, to_col):
        if board.get_cell(row, col) is not None:
            return False
        row += step_row
        col += step_col
    return True


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


class MovementRules:
    def __init__(self, rules=None, sliding_piece_types=None):
        self._rules = dict(rules if rules is not None else DEFAULT_MOVEMENT_RULES)
        self._sliding_piece_types = set(
            sliding_piece_types if sliding_piece_types is not None else DEFAULT_SLIDING_PIECE_TYPES
        )

    def is_legal(
        self,
        piece_type,
        dr,
        dc,
        color=None,
        target_piece=None,
        board=None,
        from_row=None,
        from_col=None,
        to_row=None,
        to_col=None,
    ):
        """Return True if the move is legal for piece_type.

        For context-free pieces (K, Q, R, B, N) only dr/dc matter.
        For context-dependent pieces (P) color, target_piece, board, and
        position are also used. Game always calls this single method - it
        never needs to know which piece types need extra context.
        """
        if piece_type == PAWN_PIECE_TYPE:
            return is_pawn_move(
                dr,
                dc,
                color,
                target_piece,
                board=board,
                from_row=from_row,
                from_col=from_col,
                to_col=to_col,
            )
        rule = self._rules.get(piece_type)
        return rule is not None and rule(dr, dc)

    def requires_clear_path(self, piece_type):
        """Return True if piece_type slides (so blockers must be checked)."""
        return piece_type in self._sliding_piece_types

    def register(self, piece_type, rule, sliding=False):
        """Add or replace the movement rule for a piece type.

        This is the extension point a future "design your own game"
        feature needs: it can register entirely custom piece types (e.g.
        a "drone") with their own shape function - and say whether it
        slides (needs a clear path) or jumps - without editing this class
        or Game at all.
        """
        self._rules[piece_type] = rule
        if sliding:
            self._sliding_piece_types.add(piece_type)
        else:
            self._sliding_piece_types.discard(piece_type)
