import pytest

from kongfu_chess.board import Board
from kongfu_chess.errors import (
    EmptyBoardError,
    RowWidthMismatchError,
    UnknownTokenError,
)


def test_builds_board_with_correct_dimensions():
    rows = [["wR", "wN", "."], [".", ".", "."], ["bR", "bN", "."]]
    board = Board(rows)
    assert board.num_rows == 3
    assert board.num_cols == 3


def test_get_cell_returns_none_for_empty_token():
    board = Board([["."]])
    assert board.get_cell(0, 0) is None


def test_get_cell_returns_piece_for_occupied_cell():
    board = Board([["wK"]])
    piece = board.get_cell(0, 0)
    assert piece.color == "w"
    assert piece.piece_type == "K"


def test_empty_board_raises_empty_board_error():
    with pytest.raises(EmptyBoardError):
        Board([])


def test_row_width_mismatch_raises_error():
    with pytest.raises(RowWidthMismatchError):
        Board([["wK", "."], ["."]])


def test_unknown_token_raises_error():
    with pytest.raises(UnknownTokenError) as excinfo:
        Board([["zz"]])
    assert excinfo.value.token == "zz"


def test_malformed_token_length_raises_unknown_token_error():
    with pytest.raises(UnknownTokenError):
        Board([["w"]])


def test_repr_reports_dimensions():
    board = Board([["."]])
    assert repr(board) == "Board(1x1)"


def test_board_accepts_custom_rule_set_for_future_custom_games():
    # A future "design your own game" board could use non-standard piece
    # types/colors; Board must honour whatever rule-set it is given.
    rows = [["gD"]]
    board = Board(rows, valid_colors={"g"}, valid_piece_types={"D"})
    piece = board.get_cell(0, 0)
    assert piece.piece_type == "D"


def test_board_internal_cells_are_not_exposed_directly():
    # Encapsulation check: there is no public attribute exposing the raw
    # internal storage - only the accessor methods.
    board = Board([["."]])
    assert not hasattr(board, "cells")


def test_render_rows_produces_canonical_single_space_separated_tokens():
    board = Board([["wK", "."], [".", "bK"]])
    assert board.render_rows() == ["wK .", ". bK"]


def test_render_rows_normalizes_raw_input_regardless_of_original_spacing():
    # Canonical form is rebuilt from validated Piece state, not the raw
    # input string, so it doesn't matter how the original tokens were
    # spaced - the output is always single-space separated.
    board = Board([["wK", "wQ", "."]])
    assert board.render_rows() == ["wK wQ ."]
def test_in_bounds_true_for_a_real_cell():
    board = Board([["wK", "."], [".", "bK"]])
    assert board.in_bounds(0, 0) is True
    assert board.in_bounds(1, 1) is True


def test_in_bounds_false_outside_the_grid():
    board = Board([["wK", "."], [".", "bK"]])
    assert board.in_bounds(-1, 0) is False
    assert board.in_bounds(0, -1) is False
    assert board.in_bounds(2, 0) is False
    assert board.in_bounds(0, 2) is False


def test_move_piece_relocates_piece_and_empties_source_cell():
    board = Board([["wK", "."], [".", "bK"]])
    board.move_piece(0, 0, 0, 1)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 1).token == "wK"


def test_move_piece_onto_occupied_cell_captures_it():
    board = Board([["wK", "bQ"]])
    board.move_piece(0, 0, 0, 1)
    assert board.get_cell(0, 1).token == "wK"


def test_move_piece_with_promotion_places_promoted_type():
    board = Board([[".", "wP"]])
    board.move_piece(0, 1, 0, 0, promotion_piece_type="Q")
    assert board.get_cell(0, 0).token == "wQ"
    assert board.get_cell(0, 1) is None
