from dataclasses import FrozenInstanceError

import pytest

from kongfu_chess.model.board import Board
from kongfu_chess.model.captured_piece import CapturedPiece
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


def test_game_state_initializes_scores_from_custom_board_colors():
    board = Board(
        [["rK", "gK"]],
        valid_colors={"r", "g"},
    )

    state = GameState(board=board)
    state.add_score("g", 4)

    assert state.score_by_color == {"r": 0, "g": 4}


def test_game_facade_can_override_player_colors():
    from kongfu_chess.game import Game

    board = Board([["wK"]])
    game = Game(board, player_colors={"team_a", "team_b"})

    assert game.state.score_by_color == {"team_a": 0, "team_b": 0}


def test_game_state_has_no_legacy_completed_move_writer():
    state = GameState(board=Board([["wK"]]))

    assert not hasattr(state, "record_completed_move")


def test_record_capture_stores_an_immutable_piece_snapshot():
    board = Board([["wK", "bP"]])
    state = GameState(board=board)
    captured_piece = board.get_cell(0, 1)

    state.record_capture(captured_piece, 0, 1)

    capture = state.captured_pieces[0]
    assert capture == CapturedPiece(
        piece_id=captured_piece.piece_id,
        token="bP",
        row=0,
        col=1,
    )
    assert capture.position == (0, 1)
    with pytest.raises(FrozenInstanceError):
        capture.row = 2
