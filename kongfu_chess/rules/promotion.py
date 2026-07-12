"""Pawn promotion resolution and validation."""

try:
    from ..config import DEFAULT_PROMOTION_PIECE_TYPE, PAWN_PIECE_TYPE
    from ..errors import InvalidPromotionTypeError
    from .pawn import is_promotion_row
except ImportError:
    from config import DEFAULT_PROMOTION_PIECE_TYPE, PAWN_PIECE_TYPE
    from errors import InvalidPromotionTypeError
    from pawn import is_promotion_row


def validate_promotion_piece_type(piece_type, piece_rules):
    """Return a valid promotion piece type or raise InvalidPromotionTypeError."""
    if piece_type not in piece_rules.allowed_promotion_types():
        raise InvalidPromotionTypeError(piece_type)
    return piece_type


def resolve_promotion_piece_type(
    moving_piece,
    to_row,
    num_rows,
    piece_rules,
    chosen_type=None,
    custom_policy=None,
):
    """Return the piece type a pawn promotes to, or None when no promotion applies."""
    if custom_policy is not None:
        return custom_policy(moving_piece, to_row, num_rows, chosen_type=chosen_type)

    if moving_piece is None or moving_piece.piece_type != PAWN_PIECE_TYPE:
        return None
    if not is_promotion_row(to_row, num_rows):
        return None

    if chosen_type is None:
        return DEFAULT_PROMOTION_PIECE_TYPE

    return validate_promotion_piece_type(chosen_type, piece_rules)
