"""The game board."""

try:
    from ..config import EMPTY_CELL_TOKEN, DEFAULT_VALID_COLORS, DEFAULT_VALID_PIECE_TYPES
    from ..errors import (
        DuplicateOccupancyError,
        DuplicatePieceIdError,
        EmptyBoardError,
        RowWidthMismatchError,
        UnknownTokenError,
    )
    from .piece import Piece
except ImportError:
    from config import EMPTY_CELL_TOKEN, DEFAULT_VALID_COLORS, DEFAULT_VALID_PIECE_TYPES
    from errors import (
        DuplicateOccupancyError,
        DuplicatePieceIdError,
        EmptyBoardError,
        RowWidthMismatchError,
        UnknownTokenError,
    )
    from piece import Piece


class Board:
    def __init__(
        self,
        rows_of_tokens,
        valid_colors=DEFAULT_VALID_COLORS,
        valid_piece_types=DEFAULT_VALID_PIECE_TYPES,
    ):
        self._valid_colors = valid_colors
        self._valid_piece_types = valid_piece_types
        self._next_piece_id = 0
        self._piece_ids = set()
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

        piece = Piece.from_token(token, piece_id=self._next_piece_id)
        self._next_piece_id += 1
        if piece is None or not piece.is_valid(self._valid_colors, self._valid_piece_types):
            raise UnknownTokenError(token)
        self._register_piece_id(piece.piece_id)
        return piece

    def _register_piece_id(self, piece_id):
        if piece_id in self._piece_ids:
            raise DuplicatePieceIdError(piece_id)
        self._piece_ids.add(piece_id)

    def place_piece(self, row, col, piece):
        """Place ``piece`` at ``(row, col)`` if the cell is empty.

        Raises DuplicateOccupancyError when the cell is occupied and
        DuplicatePieceIdError when ``piece.piece_id`` is already on the board.
        """
        if not self.in_bounds(row, col):
            raise IndexError(f"Cell ({row}, {col}) is out of bounds")
        if self._cells[row][col] is not None:
            raise DuplicateOccupancyError(row, col)
        if piece.piece_id is not None:
            self._register_piece_id(piece.piece_id)
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
        if piece is not None and piece.piece_id is not None:
            self._piece_ids.discard(piece.piece_id)
        self._cells[row][col] = None

    def in_bounds(self, row, col):
        return 0 <= row < self.num_rows and 0 <= col < self.num_cols

    def move_piece(self, from_row, from_col, to_row, to_col, promotion_piece_type=None):
        piece = self._cells[from_row][from_col]
        if promotion_piece_type is not None:
            piece = piece.with_piece_type(promotion_piece_type)
        self._cells[to_row][to_col] = piece
        self._cells[from_row][from_col] = None

    def render_rows(self):
        rows = []
        for row_cells in self._cells:
            tokens = [cell.token if cell is not None else EMPTY_CELL_TOKEN for cell in row_cells]
            rows.append(" ".join(tokens))
        return rows

    def __repr__(self):
        return f"Board({self.num_rows}x{self.num_cols})"
