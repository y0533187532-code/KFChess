try:
    from ..config import (
        BISHOP_PIECE_TYPE,
        KING_PIECE_TYPE,
        KNIGHT_PIECE_TYPE,
        QUEEN_PIECE_TYPE,
        ROOK_PIECE_TYPE,
    )
except ImportError:
    from config import (
        BISHOP_PIECE_TYPE,
        KING_PIECE_TYPE,
        KNIGHT_PIECE_TYPE,
        QUEEN_PIECE_TYPE,
        ROOK_PIECE_TYPE,
    )


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


DEFAULT_SHAPE_RULES = {
    KING_PIECE_TYPE: is_king_move,
    ROOK_PIECE_TYPE: is_rook_move,
    BISHOP_PIECE_TYPE: is_bishop_move,
    KNIGHT_PIECE_TYPE: is_knight_move,
    QUEEN_PIECE_TYPE: is_queen_move,
}
