"""Per-piece movement geometry (Strategy pattern)."""

try:
    from ..config import (
        DEFAULT_NON_PROMOTABLE_PROMOTION_TYPES,
        DEFAULT_PAWN_FORWARD_BY_COLOR,
        DEFAULT_PAWN_START_ROW_BY_COLOR,
        PAWN_PIECE_TYPE,
    )
    from ..model.position import Position
    from .path import is_path_clear
    from .pawn import is_pawn_move
    from .shapes import DEFAULT_SHAPE_RULES
except ImportError:
    from config import (
        DEFAULT_NON_PROMOTABLE_PROMOTION_TYPES,
        DEFAULT_PAWN_FORWARD_BY_COLOR,
        DEFAULT_PAWN_START_ROW_BY_COLOR,
        PAWN_PIECE_TYPE,
    )
    from model.position import Position
    from path import is_path_clear
    from pawn import is_pawn_move
    from shapes import DEFAULT_SHAPE_RULES


DEFAULT_SLIDING_PIECE_TYPES = frozenset({"R", "B", "Q"})


class PieceRules:
    def __init__(
        self,
        shape_rules=None,
        sliding_piece_types=None,
        pawn_forward_by_color=None,
        pawn_start_row_by_color=None,
        promotable_piece_types=None,
        non_promotable_piece_types=None,
    ):
        self._shape_rules = dict(shape_rules if shape_rules is not None else DEFAULT_SHAPE_RULES)
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
        self._non_promotable_piece_types = set(
            non_promotable_piece_types
            if non_promotable_piece_types is not None
            else DEFAULT_NON_PROMOTABLE_PROMOTION_TYPES
        )
        self._promotable_override = promotable_piece_types is not None
        if self._promotable_override:
            self._promotable_piece_types = set(promotable_piece_types)
        else:
            self._promotable_piece_types = None
            self._promotion_exclusions = set()

    def allowed_promotion_types(self):
        """Return piece types a pawn may promote into for this rule set."""
        if self._promotable_override:
            return frozenset(self._promotable_piece_types)
        return frozenset(
            self._shape_rules.keys()
            - self._non_promotable_piece_types
            - self._promotion_exclusions
        )

    def is_legal_shape(
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
        rule = self._shape_rules.get(piece_type)
        return rule is not None and rule(dr, dc)

    def requires_clear_path(self, piece_type):
        return piece_type in self._sliding_piece_types

    def is_legal_move(self, board, piece, from_row, from_col, to_row, to_col):
        if piece is None:
            return False
        dr, dc = to_row - from_row, to_col - from_col
        target_piece = board.get_cell(to_row, to_col)
        if not self.is_legal_shape(
            piece.piece_type,
            dr,
            dc,
            color=piece.color,
            target_piece=target_piece,
            board=board,
            from_row=from_row,
            from_col=from_col,
            to_row=to_row,
            to_col=to_col,
        ):
            return False
        if self.requires_clear_path(piece.piece_type):
            return is_path_clear(board, from_row, from_col, to_row, to_col)
        return True

    def legal_destinations(self, board, piece, from_row, from_col):
        destinations = set()
        for to_row in range(board.num_rows):
            for to_col in range(board.num_cols):
                if self.is_legal_move(board, piece, from_row, from_col, to_row, to_col):
                    target = board.get_cell(to_row, to_col)
                    if target is None or target.color != piece.color:
                        destinations.add(Position(to_row, to_col))
        return destinations

    def register(self, piece_type, rule, sliding=False, promotable=True):
        self._shape_rules[piece_type] = rule
        if sliding:
            self._sliding_piece_types.add(piece_type)
        else:
            self._sliding_piece_types.discard(piece_type)

        if piece_type in self._non_promotable_piece_types:
            return

        if self._promotable_override:
            if promotable:
                self._promotable_piece_types.add(piece_type)
            else:
                self._promotable_piece_types.discard(piece_type)
        elif promotable:
            self._promotion_exclusions.discard(piece_type)
        else:
            self._promotion_exclusions.add(piece_type)
