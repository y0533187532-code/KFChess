"""Print logical board occupancy as canonical row strings."""

try:
    from ..config import EMPTY_CELL_TOKEN
    from ..model.piece import PIECE_STATE_CAPTURED
except ImportError:
    from config import EMPTY_CELL_TOKEN
    from model.piece import PIECE_STATE_CAPTURED


class BoardPrinter:
    def render_rows(self, source):
        """Return canonical row strings from a Board, GameSnapshot, or GameState."""
        if hasattr(source, "board_width") and hasattr(source, "pieces"):
            return self._rows_from_snapshot(source)
        if hasattr(source, "board"):
            return source.board.render_rows()
        if hasattr(source, "render_rows"):
            return source.render_rows()
        raise TypeError(f"Unsupported board print source: {type(source)!r}")

    def _rows_from_snapshot(self, snapshot):
        grid = [
            [EMPTY_CELL_TOKEN] * snapshot.board_width
            for _ in range(snapshot.board_height)
        ]
        for piece in snapshot.pieces:
            if getattr(piece, "state", "idle") == PIECE_STATE_CAPTURED:
                continue
            grid[piece.row][piece.col] = piece.token
        return [" ".join(row) for row in grid]

    def print(self, source, stdout):
        """Write canonical row strings to stdout."""
        for row in self.render_rows(source):
            print(row, file=stdout)
