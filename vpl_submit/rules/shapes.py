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
    "K": is_king_move,
    "R": is_rook_move,
    "B": is_bishop_move,
    "N": is_knight_move,
    "Q": is_queen_move,
}
