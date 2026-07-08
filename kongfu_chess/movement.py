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


# Default rule-set for the five piece types this iteration covers. Pawn is
# intentionally absent (out of scope for now) - MovementRules.is_legal
# treats "no rule registered" as "illegal", so clicking a pawn is safely
# ignored rather than raising an error.
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


class MovementRules:
    def __init__(self, rules=None, sliding_piece_types=None):
        self._rules = dict(rules if rules is not None else DEFAULT_MOVEMENT_RULES)
        self._sliding_piece_types = set(
            sliding_piece_types if sliding_piece_types is not None else DEFAULT_SLIDING_PIECE_TYPES
        )

    def is_legal(self, piece_type, dr, dc):
        """Return True if moving by (dr, dc) is a legal shape for piece_type.

        A piece type with no registered rule (e.g. pawn, today) is simply
        not legal yet - this never raises, so an unsupported piece type
        is safely ignored rather than crashing the game loop.
        """
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
