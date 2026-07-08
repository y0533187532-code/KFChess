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


class MovementRules:
    def __init__(self, rules=None):
        self._rules = dict(rules if rules is not None else DEFAULT_MOVEMENT_RULES)

    def is_legal(self, piece_type, dr, dc):
        """Return True if moving by (dr, dc) is a legal shape for piece_type.

        A piece type with no registered rule (e.g. pawn, today) is simply
        not legal yet - this never raises, so an unsupported piece type
        is safely ignored rather than crashing the game loop.
        """
        rule = self._rules.get(piece_type)
        return rule is not None and rule(dr, dc)

    def register(self, piece_type, rule):
        """Add or replace the movement rule for a piece type.

        This is the extension point a future "design your own game"
        feature needs: it can register entirely custom piece types (e.g.
        a "drone") with their own shape function, without editing this
        class or Game at all.
        """
        self._rules[piece_type] = rule
