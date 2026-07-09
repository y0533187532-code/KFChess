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


# Default rule-set for the five non-pawn piece types.
# Pawn is absent here because its rule needs context (color + target_piece)
# that the plain (dr, dc) signature cannot carry. MovementRules.is_legal
# handles pawn transparently via is_pawn_move, so callers never need to
# know which piece types are "special".
DEFAULT_MOVEMENT_RULES = {
    "K": is_king_move,
    "R": is_rook_move,
    "B": is_bishop_move,
    "N": is_knight_move,
    "Q": is_queen_move,
}
