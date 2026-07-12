"""Print logical board occupancy as canonical row strings."""


class BoardPrinter:
    def render_rows(self, board):
        """Return canonical row strings for the given board."""
        return board.render_rows()

    def print(self, board, stdout):
        """Write canonical row strings to stdout."""
        for row in self.render_rows(board):
            print(row, file=stdout)
