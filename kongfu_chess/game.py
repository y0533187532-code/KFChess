"""Game-state transitions driven by the click/wait protocol.

A Game only knows how to react to two kinds of events - a click, and time
passing - and how that changes selection/board state. It never touches the
raw board grid directly (encapsulation): it moves pieces only through the
Board's own public API (``get_cell`` / ``in_bounds`` / ``move_piece``).

This iteration only wires "click -> select or move" together. Cooldown and
real travel-time-before-the-piece-arrives (see the requirements doc,
sections 2.1/2.2) are *not* implemented yet - ``handle_wait`` is a
deliberate no-op hook for now, kept here (rather than left out entirely) so
the future real-time engine has an obvious, single place to plug into
without CommandRunner or main.py needing to change.
"""

from .config import CELL_SIZE_PX


class Game:
    def __init__(self, board):
        self._board = board
        self._selected = None  # None, or a (row, col) tuple

    def handle_click(self, pixel_x, pixel_y):
        """Handle a click at the given pixel coordinates.

        - Clicking outside the board is ignored.
        - Clicking a piece with nothing selected selects it.
        - Clicking an empty cell with nothing selected is ignored.
        - Clicking another friendly piece while one is selected replaces
          the selection.
        - Otherwise, the selected piece moves to the clicked cell.
        """
        row, col = self._pixel_to_cell(pixel_x, pixel_y)
        if not self._board.in_bounds(row, col):
            return

        clicked_piece = self._board.get_cell(row, col)

        if self._selected is None:
            if clicked_piece is not None:
                self._selected = (row, col)
            return

        if clicked_piece is not None and clicked_piece.color == self._selected_piece.color:
            self._selected = (row, col)
        else:
            self._move_selected_to(row, col)

    def handle_wait(self, milliseconds):
        """Advance the game clock by ``milliseconds``.

        No-op for now (see module docstring) - reserved for the real-time
        move/cooldown engine.
        """

    @property
    def _selected_piece(self):
        row, col = self._selected
        return self._board.get_cell(row, col)

    def _move_selected_to(self, row, col):
        from_row, from_col = self._selected
        self._board.move_piece(from_row, from_col, row, col)
        self._selected = None

    def _pixel_to_cell(self, pixel_x, pixel_y):
        return pixel_y // CELL_SIZE_PX, pixel_x // CELL_SIZE_PX
