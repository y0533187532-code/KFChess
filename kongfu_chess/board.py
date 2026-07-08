"""The game board.

Design notes for two known-but-not-yet-implemented future needs:

* Binary board representation: the internal cell storage (``self._cells``)
  is a private attribute. Nothing outside this class ever touches it
  directly - all access goes through ``get_cell`` / ``num_rows`` /
  ``num_cols``. When a compact/binary representation is introduced, only
  the body of this class needs to change; every caller keeps working
  against the same public interface.

* Custom games / custom piece sets: ``valid_colors`` and
  ``valid_piece_types`` are constructor parameters (with the standard
  chess rule-set as their default). The board never hard-codes which
  colors or piece types are legal, so a "design your own game" feature can
  build a Board with a different rule-set without any change here.
"""

from .config import EMPTY_CELL_TOKEN, DEFAULT_VALID_COLORS, DEFAULT_VALID_PIECE_TYPES
from .errors import EmptyBoardError, RowWidthMismatchError, UnknownTokenError
from .piece import Piece


class Board:
    def __init__(
        self,
        rows_of_tokens,
        valid_colors=DEFAULT_VALID_COLORS,
        valid_piece_types=DEFAULT_VALID_PIECE_TYPES,
    ):
        self._valid_colors = valid_colors
        self._valid_piece_types = valid_piece_types
        self._cells = self._build_cells(rows_of_tokens)

    def _build_cells(self, rows_of_tokens):
        if not rows_of_tokens:
            raise EmptyBoardError()

        expected_width = len(rows_of_tokens[0])
        cells = []
        for row_tokens in rows_of_tokens:
            if len(row_tokens) != expected_width:
                raise RowWidthMismatchError()
            cells.append([self._parse_token(token) for token in row_tokens])
        return cells

    def _parse_token(self, token):
        if token == EMPTY_CELL_TOKEN:
            return None

        piece = Piece.from_token(token)
        if piece is None or not piece.is_valid(self._valid_colors, self._valid_piece_types):
            raise UnknownTokenError(token)
        return piece

    @property
    def num_rows(self):
        return len(self._cells)

    @property
    def num_cols(self):
        return len(self._cells[0]) if self._cells else 0

    def get_cell(self, row, col):
        """Return the Piece at (row, col), or None if the cell is empty."""
        return self._cells[row][col]
    def in_bounds(self, row, col):
        """Return True if (row, col) is a real cell on this board.

        Centralizing this check here (rather than each caller re-deriving
        it from num_rows/num_cols) keeps the board's own dimensions as the
        single source of truth for what counts as "on the board".
        """
        return 0 <= row < self.num_rows and 0 <= col < self.num_cols

    def move_piece(self, from_row, from_col, to_row, to_col, promotion_piece_type=None):
        """Move whatever occupies (from_row, from_col) to (to_row, to_col).

        The destination is simply overwritten (a capture), and the source
        cell becomes empty. When ``promotion_piece_type`` is set the moving
        piece is placed as that type (same color) instead of its original
        type - used for pawn promotion on the last row.
        """
        piece = self._cells[from_row][from_col]
        if promotion_piece_type is not None:
            piece = Piece(color=piece.color, piece_type=promotion_piece_type)
        self._cells[to_row][to_col] = piece
        self._cells[from_row][from_col] = None
    def render_rows(self):
        """Return the board as a list of canonical row strings.

        Each row is rebuilt from the validated Piece objects (or the empty
        token), tokens separated by a single space. Because this reads
        from validated internal state rather than the original raw input
        text, the result is always normalized - this IS the "canonical
        form" the assignment asks for.
        """
        rows = []
        for row_cells in self._cells:
            tokens = [cell.token if cell is not None else EMPTY_CELL_TOKEN for cell in row_cells]
            rows.append(" ".join(tokens))
        return rows

    def __repr__(self):
        return f"Board({self.num_rows}x{self.num_cols})"
