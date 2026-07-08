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


def test_rook_move_in_a_straight_line_is_legal():
    board, game = make_game([["wR", ".", "."]])
    game.handle_click(50, 50)
    game.handle_click(250, 50)  # two cells over on the same row
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 2).token == "wR"


def test_rook_move_diagonally_is_illegal_and_ignored():
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)  # select rook at (0, 0)
    game.handle_click(250, 250)  # diagonal to (2, 2) - illegal shape for a rook

    assert board.get_cell(0, 0).token == "wR"  # never moved
    assert board.get_cell(2, 2) is None


def test_king_moving_two_cells_is_illegal_and_ignored():
    board, game = make_game([["wK", ".", "."]])
    game.handle_click(50, 50)
    game.handle_click(250, 50)  # two cells over - illegal for a king

    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 2) is None


def test_bishop_diagonal_move_is_legal():
    rows = [["wB", ".", "."], [".", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)
    game.handle_click(250, 250)  # (2, 2) - diagonal
    assert board.get_cell(2, 2).token == "wB"


def test_knight_l_shaped_move_is_legal():
    rows = [["wN", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)
    game.handle_click(250, 150)  # (1, 2) - L shape
    assert board.get_cell(1, 2).token == "wN"


def test_queen_diagonal_and_straight_moves_are_both_legal():
    rows = [["wQ", ".", "."], [".", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)
    game.handle_click(50, 250)  # straight down (2, 0)
    assert board.get_cell(2, 0).token == "wQ"


def test_unsupported_piece_type_move_is_ignored_not_crashed():
    # Pawn ("P") has no registered movement rule yet - must be treated as
    # an illegal move (ignored), never raise.
    board, game = make_game([["wP", ".", "."]])
    game.handle_click(50, 50)
    game.handle_click(150, 50)
    assert board.get_cell(0, 0).token == "wP"
    assert board.get_cell(0, 1) is None


def test_game_accepts_custom_movement_rules_for_future_custom_games():
    from kongfu_chess.movement import MovementRules

    rules = MovementRules()
    rules.register("D", lambda dr, dc: max(abs(dr), abs(dc)) <= 2)

    rows = [["wD", ".", ".", "."], [".", ".", ".", "."], [".", ".", ".", "."]]
    board = Board(rows, valid_piece_types={"D"})
    game = Game(board, movement_rules=rules)

    game.handle_click(50, 50)
    game.handle_click(50, 250)  # 2 cells down - legal for the custom "D" rule
    assert board.get_cell(2, 0).token == "wD"


def test_handle_wait_is_a_no_op_hook_for_now():
    board, game = make_game([["wK"]])
    game.handle_wait(500)
    assert board.get_cell(0, 0).token == "wK"


def test_rook_cannot_move_through_a_blocking_piece():
    rows = [["wR", "wN", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)  # select rook at (0, 0)
    game.handle_click(350, 50)  # try to jump over the knight to (0, 3)

    assert board.get_cell(0, 0).token == "wR"  # never moved
    assert board.get_cell(0, 3) is None


def test_bishop_cannot_move_through_a_blocking_piece():
    rows = [["wB", ".", "."], [".", "bN", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)  # select bishop at (0, 0)
    game.handle_click(250, 250)  # try to move to (2, 2), through (1, 1)

    assert board.get_cell(0, 0).token == "wB"  # never moved
    assert board.get_cell(2, 2) is None


def test_knight_can_jump_over_a_blocking_piece():
    rows = [["wN", "bQ", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)  # select knight at (0, 0)
    game.handle_click(250, 150)  # jump to (1, 2) - blocker at (0,1) is irrelevant

    assert board.get_cell(0, 0) is None
    assert board.get_cell(1, 2).token == "wN"
    assert board.get_cell(0, 1).token == "bQ"  # blocker untouched


def test_piece_cannot_capture_its_own_color():
    board, game = make_game([["wR", "wN", "."]])
    game.handle_click(50, 50)  # select rook
    game.handle_click(150, 50)  # click own knight -> reselect, not a capture

    assert board.get_cell(0, 0).token == "wR"  # rook stayed
    assert board.get_cell(0, 1).token == "wN"  # knight stayed


def test_piece_can_capture_an_enemy_piece_at_the_destination():
    board, game = make_game([["wR", ".", "bN"]])
    game.handle_click(50, 50)  # select rook
    game.handle_click(250, 50)  # move onto the enemy knight - clear path

    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 2).token == "wR"
