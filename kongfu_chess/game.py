"""Game-state transitions driven by the click/wait protocol.

A Game only knows how to react to two kinds of events - a click, and time
passing - and how that changes selection/board state. It never touches the
raw board grid directly (encapsulation): it moves pieces only through the
Board's own public API (``get_cell`` / ``in_bounds`` / ``move_piece``).

This iteration adds move legality: a click that would move the selected
piece is only actually applied if ``MovementRules`` says the shape is
legal for that piece type; an illegal-shaped move just clears the
selection, same as before. ``movement_rules`` is a constructor parameter
(defaulting to the standard rule-set), the same pattern Board already
uses for ``valid_colors``/``valid_piece_types`` - a future "design your
own game" feature can hand Game a custom ``MovementRules`` instance
without any change here.

Cooldown and real travel-time-before-the-piece-arrives (see the
requirements doc, sections 2.1/2.2) are *not* implemented yet -
``handle_wait`` is a deliberate no-op hook for now, kept here (rather
than left out entirely) so the future real-time engine has an obvious,
single place to plug into without CommandRunner or main.py needing to
change.
"""

from .config import CELL_SIZE_PX
from .movement import MovementRules, is_path_clear


class Game:
    def __init__(self, board, movement_rules=None):
        self._board = board
        self._movement_rules = movement_rules or MovementRules()
        self._selected = None  # None, or a (row, col) tuple

    def handle_click(self, pixel_x, pixel_y):
        """Handle a click at the given pixel coordinates.

        - Clicking outside the board is ignored.
        - Clicking a piece with nothing selected selects it.
        - Clicking an empty cell with nothing selected is ignored.
        - Clicking another friendly piece while one is selected replaces
          the selection.
        - Otherwise, a move is attempted: it is applied only if it is a
          legal shape for the selected piece's type, and the selection is
          cleared either way.
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
            self._attempt_move_to(row, col)

    def handle_wait(self, milliseconds):
        """Advance the game clock by ``milliseconds``.

        No-op for now (see module docstring) - reserved for the real-time
        move/cooldown engine.
        """

    @property
    def _selected_piece(self):
        row, col = self._selected
        return self._board.get_cell(row, col)

    def _attempt_move_to(self, row, col):
        from_row, from_col = self._selected
        piece = self._selected_piece
        dr, dc = row - from_row, col - from_col
        target_piece = self._board.get_cell(row, col)

        if self._movement_rules.is_legal(
            piece.piece_type, dr, dc, color=piece.color, target_piece=target_piece
        ) and self._path_is_clear(piece.piece_type, from_row, from_col, row, col):
            self._board.move_piece(from_row, from_col, row, col)

        self._selected = None

    def _path_is_clear(self, piece_type, from_row, from_col, row, col):
        if not self._movement_rules.requires_clear_path(piece_type):
            return True
        return is_path_clear(self._board, from_row, from_col, row, col)

    def _pixel_to_cell(self, pixel_x, pixel_y):
        return pixel_y // CELL_SIZE_PX, pixel_x // CELL_SIZE_PX
