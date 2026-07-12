from kongfu_chess.input.controller import Controller
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState


class FakeGame:
    def __init__(self, state):
        self.state = state
        self.move_requests = []
        self.jump_requests = []
        self.moving = set()

    def moving_origins(self):
        return self.moving

    def request_move_to(self, row, col):
        self.move_requests.append((row, col))
        self.state.clear_selection()

    def request_jump(self, from_row, from_col):
        self.jump_requests.append((from_row, from_col))
        self.state.clear_selection()


def make_controller(rows):
    board = Board(rows)
    state = GameState(board=board)
    game = FakeGame(state)
    return board, state, game, Controller(board, state, game)


def test_first_click_on_piece_selects_it():
    board, state, game, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    assert state.selected == (0, 0)
    assert game.move_requests == []


def test_first_click_on_empty_cell_does_nothing():
    board, state, game, controller = make_controller([[".", "wK"]])
    controller.click(50, 50)
    assert state.selected is None
    assert game.move_requests == []


def test_outside_click_with_no_selection_is_ignored():
    board, state, game, controller = make_controller([["wK", "."]])
    controller.click(350, 50)
    assert state.selected is None
    assert game.move_requests == []


def test_second_click_sends_move_request_and_clears_selection():
    board, state, game, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    controller.click(150, 50)
    assert game.move_requests == [(0, 1)]
    assert state.selected is None


def test_friendly_reselect_does_not_send_move_request():
    board, state, game, controller = make_controller([["wK", "wQ", "."]])
    controller.click(50, 50)
    controller.click(150, 50)
    assert game.move_requests == []
    assert state.selected == (0, 1)


def test_outside_click_with_selection_clears_selection():
    board, state, game, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    controller.click(350, 50)
    assert state.selected is None
    assert game.move_requests == []


def test_outside_click_with_selection_does_not_call_game_engine():
    board, state, game, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    controller.click(-10, 50)
    assert state.selected is None
    assert game.move_requests == []
    assert game.jump_requests == []


def test_game_over_ignores_clicks():
    board, state, game, controller = make_controller([["wK", "."]])
    state.mark_game_over()
    controller.click(50, 50)
    assert state.selected is None
    assert game.move_requests == []
