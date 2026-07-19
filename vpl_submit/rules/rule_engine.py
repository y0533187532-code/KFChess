"""Read-only move validation against the current board state."""

try:
    from ..engine.reasons import MoveReason
    from ..engine.types import MoveValidation
    from .path import is_path_clear
    from .piece_rules import PieceRules
except ImportError:
    from engine.reasons import MoveReason
    from engine.types import MoveValidation
    from rules.path import is_path_clear
    from rules.piece_rules import PieceRules


class RuleEngine:
    def __init__(self, piece_rules=None):
        self._piece_rules = piece_rules or PieceRules()

    @property
    def piece_rules(self):
        return self._piece_rules

    def validate_move(self, board, from_row, from_col, to_row, to_col):
        if not board.in_bounds(from_row, from_col) or not board.in_bounds(to_row, to_col):
            return MoveValidation(is_valid=False, reason=MoveReason.OUTSIDE_BOARD)

        piece = board.get_cell(from_row, from_col)
        if piece is None:
            return MoveValidation(is_valid=False, reason=MoveReason.EMPTY_SOURCE)

        target = board.get_cell(to_row, to_col)
        if target is not None and target.color == piece.color:
            return MoveValidation(
                is_valid=False, reason=MoveReason.FRIENDLY_DESTINATION
            )

        dr, dc = to_row - from_row, to_col - from_col
        if not self._piece_rules.is_legal_shape(
            piece.piece_type,
            dr,
            dc,
            color=piece.color,
            target_piece=target,
            board=board,
            from_row=from_row,
            from_col=from_col,
            to_row=to_row,
            to_col=to_col,
        ):
            return MoveValidation(is_valid=False, reason=MoveReason.ILLEGAL_PIECE_MOVE)

        if (
            self._piece_rules.requires_clear_path(piece.piece_type)
            and not is_path_clear(board, from_row, from_col, to_row, to_col)
        ):
            return MoveValidation(is_valid=False, reason=MoveReason.PATH_BLOCKED)

        return MoveValidation(is_valid=True, reason=MoveReason.OK)
