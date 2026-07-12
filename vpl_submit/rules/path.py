def is_path_clear(board, from_row, from_col, to_row, to_col):
    """Return True if every cell strictly between source and destination is empty."""
    step_row = (to_row > from_row) - (to_row < from_row)
    step_col = (to_col > from_col) - (to_col < from_col)

    row, col = from_row + step_row, from_col + step_col
    while (row, col) != (to_row, to_col):
        if board.get_cell(row, col) is not None:
            return False
        row += step_row
        col += step_col
    return True
