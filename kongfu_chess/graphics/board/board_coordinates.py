from kongfu_chess.config import CELL_SIZE_PX


BOARD_CELLS_PER_SIDE = 8
BOARD_SIZE_PX = CELL_SIZE_PX * BOARD_CELLS_PER_SIDE


def cell_to_pixels(row: int, col: int) -> tuple[int, int]:
    """Convert a board cell into its top-left pixel coordinates."""
    x = col * CELL_SIZE_PX
    y = row * CELL_SIZE_PX
    return x, y