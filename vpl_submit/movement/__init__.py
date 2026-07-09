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

from .pawn import is_pawn_move, is_promotion_row, pawn_start_row
from .path import is_path_clear
from .routes import get_move_route, is_route_conflict, is_swap_route
from .rules import MovementRules
from .shapes import (
    is_bishop_move,
    is_king_move,
    is_knight_move,
    is_queen_move,
    is_rook_move,
)

__all__ = [
    "MovementRules",
    "get_move_route",
    "is_bishop_move",
    "is_king_move",
    "is_knight_move",
    "is_path_clear",
    "is_pawn_move",
    "is_promotion_row",
    "is_queen_move",
    "is_route_conflict",
    "is_rook_move",
    "is_swap_route",
    "pawn_start_row",
]
