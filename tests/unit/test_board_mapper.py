from kongfu_chess.input.board_mapper import BoardMapper
from kongfu_chess.model.board import Board


def test_pixel_in_first_column_maps_to_col_zero():
    board = Board([[".", "."]])
    mapper = BoardMapper()
    cell = mapper.pixel_to_cell(50, 50, board)
    assert cell.row == 0
    assert cell.col == 0


def test_pixel_in_second_column_maps_to_col_one():
    board = Board([[".", "."]])
    mapper = BoardMapper()
    cell = mapper.pixel_to_cell(150, 50, board)
    assert cell.row == 0
    assert cell.col == 1


def test_pixel_in_second_row_maps_to_row_one():
    board = Board([["."], ["."]])
    mapper = BoardMapper()
    cell = mapper.pixel_to_cell(50, 150, board)
    assert cell.row == 1
    assert cell.col == 0


def test_out_of_bounds_click_returns_none():
    board = Board([["wK", "."]])
    mapper = BoardMapper()
    assert mapper.pixel_to_cell(350, 50, board) is None
    assert mapper.pixel_to_cell(-10, 50, board) is None


def test_boundary_pixel_at_last_valid_cell():
    board = Board([[".", "."], [".", "."]])
    mapper = BoardMapper()
    cell = mapper.pixel_to_cell(199, 199, board)
    assert cell.row == 1
    assert cell.col == 1


def test_custom_cell_size_is_used():
    board = Board([[".", "."], [".", "."]])
    mapper = BoardMapper(cell_size_px=10)

    cell = mapper.pixel_to_cell(15, 5, board)

    assert cell.row == 0
    assert cell.col == 1
