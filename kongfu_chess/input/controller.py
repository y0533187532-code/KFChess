"""Translates pixel clicks into selection and move requests."""

try:
    from .board_mapper import BoardMapper
except ImportError:
    from board_mapper import BoardMapper


class Controller:
    """Handles click selection; delegates move execution to the game engine."""

    def __init__(self, board, state, engine, mapper=None):
        self._board = board
        self._state = state
        self._engine = engine
        self._mapper = mapper or BoardMapper()

    @property
    def selected(self):
        return self._state.selected

    def click(self, pixel_x, pixel_y):
        if self._state.is_game_over:
            return

        cell = self._mapper.pixel_to_cell(pixel_x, pixel_y, self._board)
        if cell is None:
            if self._state.selected is not None:
                self._state.clear_selection()
            return

        row, col = cell.row, cell.col
        clicked_piece = self._board.get_cell(row, col)
        moving_origins = self._engine.moving_origins()

        if self._state.selected is None:
            if (
                clicked_piece is not None
                and (row, col) not in moving_origins
                and not self._engine.is_piece_resting_at(row, col)
            ):
                self._state.select(row, col)
            return

        from_row, from_col = self._state.selected
        if (from_row, from_col) in moving_origins:
            self._state.clear_selection()
            return

        if (row, col) == (from_row, from_col):
            if clicked_piece is None:
                self._state.clear_selection()
            else:
                self._engine.request_jump(from_row, from_col)
                self._state.clear_selection()
            return

        selected_piece = self._board.get_cell(from_row, from_col)
        if clicked_piece is not None and clicked_piece.color == selected_piece.color:
            if (row, col) in moving_origins:
                self._state.clear_selection()
            elif self._engine.is_piece_resting_at(row, col):
                self._state.clear_selection()
            else:
                self._state.select(row, col)
        else:
            self._engine.request_move(from_row, from_col, row, col)
            self._state.clear_selection()
