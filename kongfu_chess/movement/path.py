def is_path_clear(board, from_row, from_col, to_row, to_col):
    """Return True if every cell strictly between the two given cells is
    empty on ``board``.

    Only meaningful for a straight line or diagonal (i.e. a move already
    confirmed legal by MovementRules.is_legal for a sliding piece type) -
    it walks one step at a time toward the destination using the board's
    own public ``get_cell``, never touching board internals directly.
    """
    step_row = (to_row > from_row) - (to_row < from_row)
    step_col = (to_col > from_col) - (to_col < from_col)

    row, col = from_row + step_row, from_col + step_col
    while (row, col) != (to_row, to_col):
        if board.get_cell(row, col) is not None:
            return False
        row += step_row
        col += step_col
    return True
