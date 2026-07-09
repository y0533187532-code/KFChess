try:
    from ..config import (
        DEFAULT_PAWN_FORWARD_BY_COLOR,
        DEFAULT_PAWN_START_ROW_BY_COLOR,
        PAWN_PIECE_TYPE,
    )
    from .pawn import is_pawn_move
    from .shapes import DEFAULT_MOVEMENT_RULES
except ImportError:
    from config import (
        DEFAULT_PAWN_FORWARD_BY_COLOR,
        DEFAULT_PAWN_START_ROW_BY_COLOR,
        PAWN_PIECE_TYPE,
    )
    from .pawn import is_pawn_move
    from .shapes import DEFAULT_MOVEMENT_RULES


# Piece types that "slide" and therefore need every cell strictly between
# source and destination to be empty. Knight is deliberately absent - it
# jumps over blockers by definition, and king only ever moves one cell (no
# intermediate cell exists to check).
DEFAULT_SLIDING_PIECE_TYPES = frozenset({"R", "B", "Q"})


class MovementRules:
    def __init__(
        self,
        rules=None,
        sliding_piece_types=None,
        pawn_forward_by_color=None,
        pawn_start_row_by_color=None,
    ):
        self._rules = dict(rules if rules is not None else DEFAULT_MOVEMENT_RULES)
        self._sliding_piece_types = set(
            sliding_piece_types if sliding_piece_types is not None else DEFAULT_SLIDING_PIECE_TYPES
        )
        self._pawn_forward_by_color = dict(
            pawn_forward_by_color
            if pawn_forward_by_color is not None
            else DEFAULT_PAWN_FORWARD_BY_COLOR
        )
        self._pawn_start_row_by_color = dict(
            pawn_start_row_by_color
            if pawn_start_row_by_color is not None
            else DEFAULT_PAWN_START_ROW_BY_COLOR
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
                forward_by_color=self._pawn_forward_by_color,
                start_row_by_color=self._pawn_start_row_by_color,
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
