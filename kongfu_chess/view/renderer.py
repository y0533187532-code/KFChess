"""View adapter: render read-only GameSnapshot data without touching the model."""

from ..config import CELL_SIZE_PX, EMPTY_CELL_TOKEN
from ..engine.types import GameSnapshot
from ..model.piece import PIECE_STATE_CAPTURED


class Renderer:
    """Draws game state from a read-only snapshot. GUI wiring is out of scope."""

    def render_logical_rows(self, snapshot: GameSnapshot) -> list[str]:
        """Return canonical logical board rows derived only from the snapshot."""
        grid = [
            [EMPTY_CELL_TOKEN] * snapshot.board_width
            for _ in range(snapshot.board_height)
        ]
        for piece in snapshot.pieces:
            if getattr(piece, "state", "idle") == PIECE_STATE_CAPTURED:
                continue
            grid[piece.row][piece.col] = piece.token
        return [" ".join(row) for row in grid]

    def cell_center_pixels(self, row, col):
        """Map a board cell to the center pixel of its grid square."""
        return col * CELL_SIZE_PX + CELL_SIZE_PX // 2, row * CELL_SIZE_PX + CELL_SIZE_PX // 2

    def render(self, snapshot: GameSnapshot, stdout=None) -> list[str]:
        """Render logical board rows; optionally write them to stdout."""
        rows = self.render_logical_rows(snapshot)
        if stdout is not None:
            for row in rows:
                print(row, file=stdout)
        return rows
