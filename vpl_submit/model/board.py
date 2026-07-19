"""The game board."""

try:
    from ..config import EMPTY_CELL_TOKEN, DEFAULT_VALID_COLORS, DEFAULT_VALID_PIECE_TYPES
    from ..errors import (
        DuplicateOccupancyError,
        EmptyBoardError,
        RowWidthMismatchError,
        UnknownTokenError,
    )
    from .piece import Piece
    from .piece_registry import PieceRegistry
except ImportError:
    from config import EMPTY_CELL_TOKEN, DEFAULT_VALID_COLORS, DEFAULT_VALID_PIECE_TYPES
    from errors import (
        DuplicateOccupancyError,
        EmptyBoardError,
        RowWidthMismatchError,
        UnknownTokenError,
    )
    from piece import Piece
    from piece_registry import PieceRegistry


class Board:
    def __init__(
        self,
        rows_of_tokens,
        valid_colors=DEFAULT_VALID_COLORS,
        valid_piece_types=DEFAULT_VALID_PIECE_TYPES,
        piece_registry=None,
    ):
        self._valid_colors = valid_colors
        self._valid_piece_types = valid_piece_types
        self._piece_registry = (
            PieceRegistry() if piece_registry is None else piece_registry
        )
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
        return self._piece_registry.register(piece)

    def place_piece(self, row, col, piece):
        """Place ``piece`` at ``(row, col)`` if the cell is empty.

        Raises DuplicateOccupancyError when the cell is occupied and
        DuplicatePieceIdError when ``piece.piece_id`` was already registered
        during this game's lifetime.
        """
        if not self.in_bounds(row, col):
            raise IndexError(f"Cell ({row}, {col}) is out of bounds")
        if self._cells[row][col] is not None:
            raise DuplicateOccupancyError(row, col)
        self._cells[row][col] = self._piece_registry.register(piece)

    def restore_piece(self, row, col, piece):
        """Return the same known piece to an empty cell after temporary removal."""
        if not self.in_bounds(row, col):
            raise IndexError(f"Cell ({row}, {col}) is out of bounds")
        if self._cells[row][col] is not None:
            raise DuplicateOccupancyError(row, col)
        self._piece_registry.reactivate(piece)
        self._cells[row][col] = piece

    @property
    def num_rows(self):
        return len(self._cells)

    @property
    def num_cols(self):
        return len(self._cells[0]) if self._cells else 0

    def get_cell(self, row, col):
        """Return the Piece at (row, col), or None if the cell is empty."""
        return self._cells[row][col]

    def clear_cell(self, row, col):
        """Remove whatever occupies (row, col), leaving the cell empty."""
        piece = self._cells[row][col]
        if piece is not None:
            self._piece_registry.deactivate(piece)
        self._cells[row][col] = None

    def in_bounds(self, row, col):
        return 0 <= row < self.num_rows and 0 <= col < self.num_cols

    def move_piece(self, from_row, from_col, to_row, to_col, promotion_piece_type=None):
        piece = self._cells[from_row][from_col]
        captured_piece = self._cells[to_row][to_col]
        if captured_piece is not None and captured_piece is not piece:
            self._piece_registry.deactivate(captured_piece)
        if promotion_piece_type is not None:
            promoted_piece = piece.with_piece_type(promotion_piece_type)
            self._piece_registry.replace_piece(piece, promoted_piece)
            piece = promoted_piece
        self._cells[to_row][to_col] = piece
        if (from_row, from_col) != (to_row, to_col):
            self._cells[from_row][from_col] = None

    def render_rows(self):
        rows = []
        for row_cells in self._cells:
            tokens = [cell.token if cell is not None else EMPTY_CELL_TOKEN for cell in row_cells]
            rows.append(" ".join(tokens))
        return rows

    def __repr__(self):
        return f"Board({self.num_rows}x{self.num_cols})"
