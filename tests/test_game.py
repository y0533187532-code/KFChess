from kongfu_chess.board import Board
from kongfu_chess.game import Game


def make_game(rows):
    board = Board(rows)
    return board, Game(board)


def test_click_outside_the_board_is_ignored():
    board, game = make_game([["wK"]])
    game.handle_click(-50, -50)
    assert board.get_cell(0, 0).token == "wK"


def test_click_on_empty_cell_with_nothing_selected_is_ignored():
    board, game = make_game([[".", "wK"]])
    game.handle_click(50, 50)  # (row 0, col 0) - empty
    game.handle_click(250, 50)  # (row 0, col 2) - out of bounds, ignored too
    assert board.get_cell(0, 1).token == "wK"


def test_click_on_a_piece_selects_it_and_does_not_move_it():
    board, game = make_game([["wK", "."]])
    game.handle_click(50, 50)  # selects (0, 0)
    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 1) is None


def test_click_on_empty_cell_after_selecting_moves_the_piece():
    board, game = make_game([["wK", "."]])
    game.handle_click(50, 50)  # select wK at (0, 0)
    game.handle_click(150, 50)  # move to (0, 1)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 1).token == "wK"


def test_click_on_enemy_piece_after_selecting_captures_it():
    board, game = make_game([["wK", "bQ"]])
    game.handle_click(50, 50)  # select wK
    game.handle_click(150, 50)  # capture bQ at (0, 1)
    assert board.get_cell(0, 1).token == "wK"


def test_click_on_another_friendly_piece_replaces_the_selection():
    board, game = make_game([["wK", "wQ", "."]])
    game.handle_click(50, 50)  # select wK at (0, 0)
    game.handle_click(150, 50)  # friendly wQ at (0, 1) -> reselect, not a move
    game.handle_click(250, 50)  # move the now-selected wQ to the empty (0, 2)

    assert board.get_cell(0, 0).token == "wK"  # untouched - wK never moved
    assert board.get_cell(0, 1) is None
    assert board.get_cell(0, 2).token == "wQ"


def test_handle_wait_is_a_no_op_hook_for_now():
    board, game = make_game([["wK"]])
    game.handle_wait(500)
    assert board.get_cell(0, 0).token == "wK"
