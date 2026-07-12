"""Maps pixel coordinates to board cells (Coordinate Adapter)."""

try:
    from ..config import CELL_SIZE_PX
    from ..model.position import Position
except ImportError:
    from config import CELL_SIZE_PX
    try:
        from model.position import Position
    except ImportError:
        from position import Position


class BoardMapper:
    def __init__(self, cell_size_px=CELL_SIZE_PX):
        self._cell_size_px = cell_size_px

    def pixel_to_cell(self, pixel_x, pixel_y, board):
        """Return the board cell for a pixel click, or None if out of bounds."""
        row = pixel_y // self._cell_size_px
        col = pixel_x // self._cell_size_px
        if not board.in_bounds(row, col):
            return None
        return Position(row, col)
