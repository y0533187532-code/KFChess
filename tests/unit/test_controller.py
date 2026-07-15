from kongfu_chess.engine.types import MoveResult
from kongfu_chess.input.controller import Controller
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState


class FakeEngine:
    def __init__(self, state):
        self.state = state
        self.move_requests = []
        self.jump_requests = []
        self.moving = set()
        self.resting = set()

    def moving_origins(self):
        return self.moving

    def request_move(self, from_row, from_col, to_row, to_col):
        self.move_requests.append((from_row, from_col, to_row, to_col))
        return MoveResult(is_accepted=True, reason="ok")

    def request_jump(self, from_row, from_col):
        self.jump_requests.append((from_row, from_col))
        return MoveResult(is_accepted=True, reason="ok")

    def is_piece_resting_at(self, row, col):
        return (row, col) in self.resting


def make_controller(rows):
    board = Board(rows)
    state = GameState(board=board)
    engine = FakeEngine(state)
    return board, state, engine, Controller(board, state, engine)


def test_first_click_on_piece_selects_it():
    board, state, engine, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    assert state.selected == (0, 0)
    assert engine.move_requests == []


def test_first_click_on_empty_cell_does_nothing():
    board, state, engine, controller = make_controller([[".", "wK"]])
    controller.click(50, 50)
    assert state.selected is None
    assert engine.move_requests == []


def test_outside_click_with_no_selection_is_ignored():
    board, state, engine, controller = make_controller([["wK", "."]])
    controller.click(350, 50)
    assert state.selected is None
    assert engine.move_requests == []


def test_second_click_sends_move_request_and_clears_selection():
    board, state, engine, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    controller.click(150, 50)
    assert engine.move_requests == [(0, 0, 0, 1)]
    assert state.selected is None


def test_friendly_reselect_does_not_send_move_request():
    board, state, engine, controller = make_controller([["wK", "wQ", "."]])
    controller.click(50, 50)
    controller.click(150, 50)
    assert engine.move_requests == []
    assert state.selected == (0, 1)


def test_outside_click_with_selection_clears_selection():
    board, state, engine, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    controller.click(350, 50)
    assert state.selected is None
    assert engine.move_requests == []


def test_outside_click_with_selection_does_not_call_game_engine():
    board, state, engine, controller = make_controller([["wK", "."]])
    controller.click(50, 50)
    controller.click(-10, 50)
    assert state.selected is None
    assert engine.move_requests == []
    assert engine.jump_requests == []


def test_game_over_ignores_clicks():
    board, state, engine, controller = make_controller([["wK", "."]])
    state.mark_game_over()
    controller.click(50, 50)
    assert state.selected is None
    assert engine.move_requests == []


def test_invalid_second_click_still_clears_selection():
    board, state, engine, controller = make_controller([["wK", ".", "."]])

    class RejectingEngine(FakeEngine):
        def request_move(self, from_row, from_col, to_row, to_col):
            self.move_requests.append((from_row, from_col, to_row, to_col))
            return MoveResult(is_accepted=False, reason="illegal_piece_move")

    rejecting = RejectingEngine(state)
    controller = Controller(board, state, rejecting)
    controller.click(50, 50)
    controller.click(250, 50)
    assert rejecting.move_requests == [(0, 0, 0, 2)]
    assert state.selected is None


def test_first_click_on_resting_piece_does_not_select_it():
    _, state, engine, controller = make_controller([["wK", "."]])
    engine.resting.add((0, 0))
    controller.click(50, 50)
    assert state.selected is None
    assert engine.move_requests == []
    assert engine.jump_requests == []


def test_friendly_reselect_on_resting_piece_clears_selection():
    _, state, engine, controller = make_controller([["wK", "wQ"]])
    controller.click(50, 50)
    engine.resting.add((0, 1))
    controller.click(150, 50)
    assert state.selected is None
    assert engine.move_requests == []
