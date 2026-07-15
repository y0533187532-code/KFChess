from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.model.piece import Piece


def test_game_state_starts_not_over_with_no_selection():
    board = Board([["wK"]])
    state = GameState(board=board)
    assert state.is_game_over is False
    assert state.selected is None
    assert state.score_by_color == {"w": 0, "b": 0}


def test_game_state_mark_game_over():
    board = Board([["wK"]])
    state = GameState(board=board)
    state.mark_game_over()
    assert state.is_game_over is True


def test_game_state_select_and_clear():
    board = Board([["wK"]])
    state = GameState(board=board)
    state.select(0, 0)
    assert state.selected == (0, 0)
    state.clear_selection()
    assert state.selected is None


def test_game_uses_game_state():
    from kongfu_chess.game import Game

    board = Board([["wK"]])
    game = Game(board)
    assert game.state.board is board
    assert game.state.is_game_over is False
    assert game._controller.selected is None


def test_game_state_add_score_accumulates_points():
    board = Board([["wK"]])
    state = GameState(board=board)
    state.add_score("w", 3)
    state.add_score("w", 5)
    state.add_score("b", 1)
    assert state.score_by_color == {"w": 8, "b": 1}
