from kongfu_chess.board import Board
from kongfu_chess.config import DEFAULT_MOVE_DURATION_MS
from kongfu_chess.game import Game

FULL_MOVE_WAIT_MS = DEFAULT_MOVE_DURATION_MS["K"]


def make_game(rows):
    board = Board(rows)
    return board, Game(board)


def finish_move(game, ms=FULL_MOVE_WAIT_MS):
    game.handle_wait(ms)


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
    finish_move(game)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 1).token == "wK"


def test_click_on_enemy_piece_after_selecting_captures_it():
    board, game = make_game([["wK", "bQ"]])
    game.handle_click(50, 50)  # select wK
    game.handle_click(150, 50)  # capture bQ at (0, 1)
    finish_move(game)
    assert board.get_cell(0, 1).token == "wK"


def test_click_on_another_friendly_piece_replaces_the_selection():
    board, game = make_game([["wK", "wQ", "."]])
    game.handle_click(50, 50)  # select wK at (0, 0)
    game.handle_click(150, 50)  # friendly wQ at (0, 1) -> reselect, not a move
    game.handle_click(250, 50)  # move the now-selected wQ to the empty (0, 2)
    finish_move(game)

    assert board.get_cell(0, 0).token == "wK"  # untouched - wK never moved
    assert board.get_cell(0, 1) is None
    assert board.get_cell(0, 2).token == "wQ"


def test_rook_move_in_a_straight_line_is_legal():
    board, game = make_game([["wR", ".", "."]])
    game.handle_click(50, 50)
    game.handle_click(250, 50)  # two cells over on the same row
    finish_move(game)
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
    finish_move(game)
    assert board.get_cell(2, 2).token == "wB"


def test_knight_l_shaped_move_is_legal():
    rows = [["wN", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)
    game.handle_click(250, 150)  # (1, 2) - L shape
    finish_move(game)
    assert board.get_cell(1, 2).token == "wN"


def test_queen_diagonal_and_straight_moves_are_both_legal():
    rows = [["wQ", ".", "."], [".", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)
    game.handle_click(50, 250)  # straight down (2, 0)
    finish_move(game)
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
    game = Game(board, movement_rules=rules, move_durations={"D": FULL_MOVE_WAIT_MS})

    game.handle_click(50, 50)
    game.handle_click(50, 250)  # 2 cells down - legal for the custom "D" rule
    finish_move(game)
    assert board.get_cell(2, 0).token == "wD"


def test_handle_wait_with_no_pending_move_is_safe():
    board, game = make_game([["wK"]])
    game.handle_wait(500)
    assert board.get_cell(0, 0).token == "wK"


def test_conflicting_premove_is_rejected_while_piece_is_moving():
    rows = [["wR", ".", "bR"]]
    board, game = make_game(rows)
    game.handle_click(50, 50)    # select white rook at (0, 0)
    game.handle_click(250, 50)   # wR starts moving to (0, 2) — route includes (0,1),(0,2)
    assert board.get_cell(0, 0).token == "wR"
    game.handle_click(250, 50)   # select black rook at (0, 2)
    game.handle_click(150, 50)   # bR tries (0, 1) — overlaps white route
    finish_move(game)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 2).token == "wR"
    assert board.get_cell(0, 1) is None


def test_two_non_conflicting_moves_can_be_active_simultaneously():
    rows = [["wK", ".", ".", "bK"]]
    board, game = make_game(rows)
    game.handle_click(50, 50)    # select wK at (0, 0)
    game.handle_click(150, 50)   # wK → (0, 1)
    game.handle_click(350, 50)   # select bK at (0, 3)
    game.handle_click(250, 50)   # bK → (0, 2)
    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 3).token == "bK"
    finish_move(game)
    assert board.get_cell(0, 1).token == "wK"
    assert board.get_cell(0, 2).token == "bK"


def test_invalid_premove_rejected_when_landing_on_active_origin():
    rows = [["wR", ".", "bR"]]
    board, game = make_game(rows)
    game.handle_click(50, 50)    # wR at (0,0) starts moving right
    game.handle_click(250, 50)   # wR → (0, 2)
    game.handle_click(250, 50)   # select bR at (0,2)
    game.handle_click(50, 50)    # bR tries to land on (0,0) — white origin
    finish_move(game)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 2).token == "wR"
    assert board.get_cell(0, 1) is None


def test_cannot_select_piece_whose_origin_is_currently_moving():
    board, game = make_game([["wR", ".", "."]])
    game.handle_click(50, 50)
    game.handle_click(250, 50)   # wR moving from (0, 0)
    game.handle_click(50, 50)    # try to select (0, 0) again — ignored
    assert board.get_cell(0, 0).token == "wR"


def test_enemy_swap_premoves_are_both_accepted():
    board, game = make_game([["wK", "bK"]])
    game.handle_click(50, 50)    # wK at (0,0)
    game.handle_click(150, 50)   # wK → (0,1) — order 0
    game.handle_click(150, 50)   # bK at (0,1)
    game.handle_click(50, 50)    # bK → (0,0) — order 1, swap premove
    finish_move(game)
    # Lower order (wK) executes; higher-order swap partner is cancelled
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 1).token == "wK"


def test_friendly_route_conflict_rejected():
    rows = [["wR", ".", ".", "wQ"]]
    board, game = make_game(rows)
    game.handle_click(50, 50)    # wR at (0,0) moving to (0,2)
    game.handle_click(250, 50)
    game.handle_click(350, 50)   # select wQ at (0,3)
    game.handle_click(150, 50)   # wQ tries (0,1) — overlaps rook route
    finish_move(game)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 2).token == "wR"
    assert board.get_cell(0, 3).token == "wQ"


def test_cannot_reselect_friendly_at_moving_origin():
    rows = [["wR", ".", "."], [".", "wQ", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 50)     # select wR at (0, 0)
    game.handle_click(250, 50)    # wR moving to (0, 2)
    game.handle_click(150, 150)  # select wQ at (1, 1)
    game.handle_click(50, 50)     # click wR square — moving origin, clear selection
    assert game._selected is None


def test_wait_skips_duplicate_finish_entry():
    board, game = make_game([["wK", "."]])
    game.handle_click(50, 50)
    game.handle_click(150, 50)
    move = game._active_moves[0]
    move["remaining"] = 0
    game._active_moves.append(move)
    game.handle_wait(0)
    assert board.get_cell(0, 1).token == "wK"


def test_stale_selection_cleared_when_origin_is_moving():
    board, game = make_game([["wR", ".", "."]])
    game.handle_click(50, 50)
    game.handle_click(250, 50)   # wR moving from (0, 0)
    game._selected = (0, 0)
    game.handle_click(50, 50)    # clears stale selection
    game.handle_click(50, 50)    # cannot select moving origin
    assert board.get_cell(0, 0).token == "wR"


def test_higher_order_swap_cancelled_while_lower_order_still_active():
    board, game = make_game([["wK", "bK"]])
    game.handle_click(50, 50)
    game.handle_click(150, 50)   # wK → (0, 1), order 0, still in-flight
    game._active_moves.append(
        {
            "from": (0, 1),
            "to": (0, 0),
            "remaining": 0,
            "order": 1,
            "route": [(0, 0)],
            "color": "b",
        }
    )
    game.handle_wait(0)          # bK tries to finish while wK still active
    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 1).token == "bK"
    finish_move(game)
    assert board.get_cell(0, 1).token == "wK"
    assert board.get_cell(0, 0) is None


def test_partial_wait_does_not_complete_move():
    board, game = make_game([["wK", "."]])
    game.handle_click(50, 50)
    game.handle_click(150, 50)
    game.handle_wait(500)
    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 1) is None
    game.handle_wait(500)
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 1).token == "wK"


def test_piece_can_move_again_immediately_after_arrival():
    board, game = make_game([["wK", ".", "."]])
    game.handle_click(50, 50)
    game.handle_click(150, 50)  # move to (0, 1)
    finish_move(game)
    assert board.get_cell(0, 1).token == "wK"
    game.handle_click(150, 50)  # select at destination
    game.handle_click(250, 50)  # move to (0, 2) - no cooldown wait needed
    finish_move(game)
    assert board.get_cell(0, 2).token == "wK"


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
    finish_move(game)

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
    finish_move(game)

    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 2).token == "wR"


# --- Pawn integration tests (via Game) ---

def test_white_pawn_moves_one_cell_forward():
    rows = [[".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 150)  # select wP at (1, 1)
    game.handle_click(150, 50)   # move to (0, 1) - one step forward for white
    finish_move(game)
    assert board.get_cell(0, 1).token == "wQ"
    assert board.get_cell(1, 1) is None


def test_black_pawn_moves_one_cell_forward():
    rows = [[".", ".", "."], [".", "bP", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 150)  # select bP at (1, 1)
    game.handle_click(150, 250)  # move to (2, 1) - one step forward for black
    finish_move(game)
    assert board.get_cell(2, 1).token == "bQ"
    assert board.get_cell(1, 1) is None


def test_white_pawn_cannot_move_two_cells_from_non_start_row():
    rows = [[".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 150)  # select wP at (1, 1) - not start row
    game.handle_click(150, 50)   # try to move two cells forward to (0, 1)
    assert board.get_cell(1, 1).token == "wP"  # never moved
    assert board.get_cell(0, 1) is None


def test_white_pawn_double_step_from_start_row():
    rows = [[".", ".", "."], [".", ".", "."], [".", "wP", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 250)  # select wP at (2, 1) - start row
    game.handle_click(150, 50)   # double step to (0, 1)
    finish_move(game)
    assert board.get_cell(0, 1).token == "wQ"
    assert board.get_cell(2, 1) is None


def test_black_pawn_double_step_from_start_row():
    rows = [[".", "bP", "."], [".", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 50)   # select bP at (0, 1) - start row
    game.handle_click(150, 250)  # double step to (2, 1)
    finish_move(game)
    assert board.get_cell(2, 1).token == "bQ"
    assert board.get_cell(0, 1) is None


def test_white_pawn_double_step_rejected_when_intermediate_blocked():
    rows = [[".", ".", "."], [".", "bN", "."], [".", "wP", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 250)  # select wP at (2, 1)
    game.handle_click(150, 50)   # try double step to (0, 1)
    assert board.get_cell(2, 1).token == "wP"
    assert board.get_cell(0, 1) is None


def test_white_pawn_captures_diagonally():
    rows = [[".", "bN", "."], ["wP", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 150)   # select wP at (1, 0)
    game.handle_click(150, 50)   # capture bN at (0, 1)
    finish_move(game)
    assert board.get_cell(0, 1).token == "wQ"
    assert board.get_cell(1, 0) is None


def test_black_pawn_captures_diagonally():
    rows = [[".", ".", "."], [".", "bP", "."], ["wN", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 150)  # select bP at (1, 1)
    game.handle_click(50, 250)   # capture wN at (2, 0)
    finish_move(game)
    assert board.get_cell(2, 0).token == "bQ"
    assert board.get_cell(1, 1) is None


def test_promoted_queen_can_move_as_queen():
    rows = [[".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(150, 150)
    game.handle_click(150, 50)
    finish_move(game)
    assert board.get_cell(0, 1).token == "wQ"
    game.handle_click(150, 50)   # select promoted queen
    game.handle_click(50, 50)    # queen diagonal move to (0, 0)
    finish_move(game)
    assert board.get_cell(0, 0).token == "wQ"
    assert board.get_cell(0, 1) is None


def test_pawn_cannot_capture_forward_without_diagonal():
    rows = [["bN", ".", "."], ["wP", ".", "."], [".", ".", "."]]
    board, game = make_game(rows)
    game.handle_click(50, 150)   # select wP at (1, 0)
    game.handle_click(50, 50)    # try to capture bN directly forward - illegal
    assert board.get_cell(1, 0).token == "wP"  # never moved
    assert board.get_cell(0, 0).token == "bN"  # never captured


# --- Game over (iteration 9) ---

def test_capturing_enemy_king_ends_the_game():
    board, game = make_game([["wR", "bK"]])
    game.handle_click(50, 50)    # select wR at (0, 0)
    game.handle_click(150, 50)   # capture bK at (0, 1)
    assert not game.is_game_over
    finish_move(game)
    assert game.is_game_over
    assert board.get_cell(0, 1).token == "wR"


def test_clicks_are_ignored_after_game_over():
    board, game = make_game([["wR", "bK"], [".", "wN"]])
    game.handle_click(50, 50)    # select wR, capture bK
    game.handle_click(150, 50)
    finish_move(game)
    assert game.is_game_over
    snapshot = board.render_rows()
    game.handle_click(150, 250)  # try to select wN at (1, 1)
    game.handle_click(250, 250)  # try to move
    assert board.render_rows() == snapshot
    assert game.is_game_over


def test_game_is_not_over_when_capturing_non_king():
    board, game = make_game([["wR", "bQ"]])
    game.handle_click(50, 50)
    game.handle_click(150, 50)   # capture bQ
    finish_move(game)
    assert not game.is_game_over
    assert board.get_cell(0, 1).token == "wR"
