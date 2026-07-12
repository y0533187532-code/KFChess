"""Read-only move validation against the current board state."""

try:
    from ..engine.types import MoveValidation
    from .piece_rules import PieceRules
except ImportError:
    from engine.types import MoveValidation
    from piece_rules import PieceRules


class RuleEngine:
    def __init__(self, piece_rules=None):
        self._piece_rules = piece_rules or PieceRules()

    @property
    def piece_rules(self):
        return self._piece_rules

    def validate_move(self, board, from_row, from_col, to_row, to_col):
        if not board.in_bounds(from_row, from_col) or not board.in_bounds(to_row, to_col):
            return MoveValidation(is_valid=False, reason="outside_board")

        piece = board.get_cell(from_row, from_col)
        if piece is None:
            return MoveValidation(is_valid=False, reason="empty_source")

        target = board.get_cell(to_row, to_col)
        if target is not None and target.color == piece.color:
            return MoveValidation(is_valid=False, reason="friendly_destination")

        if not self._piece_rules.is_legal_move(
            board, piece, from_row, from_col, to_row, to_col
        ):
            return MoveValidation(is_valid=False, reason="illegal_piece_move")

        return MoveValidation(is_valid=True, reason="ok")
