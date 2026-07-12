import io

import pytest

from kongfu_chess.errors import InvalidPromotionTypeError
from kongfu_chess.model.board import Board
from kongfu_chess.texttests.script_runner import ScriptRunner
from kongfu_chess.game import Game


def make_runner(rows):
    board = Board(rows)
    game = Game(board)
    stdout = io.StringIO()
    return board, ScriptRunner(game, board, stdout), stdout


def test_blank_lines_are_ignored():
    board, runner, stdout = make_runner([["wK"]])
    runner.run(["", "   "])
    assert stdout.getvalue() == ""


def test_click_command_is_dispatched_to_the_game():
    board, runner, stdout = make_runner([["wK", "."]])
    runner.run(["click 50 50", "click 150 50", "wait 1000"])
    assert board.get_cell(0, 0) is None
    assert board.get_cell(0, 1).token == "wK"


def test_jump_command_selects_then_starts_airborne_jump():
    board, runner, stdout = make_runner([["wK"]])
    runner.run(["jump 50 50", "wait 1000"])
    assert board.get_cell(0, 0).token == "wK"
    assert not runner._game._active_moves


def test_wait_command_is_dispatched_without_error():
    board, runner, stdout = make_runner([["wK"]])
    runner.run(["wait 250"])
    assert board.get_cell(0, 0).token == "wK"


def test_print_board_command_prints_the_current_state():
    board, runner, stdout = make_runner([["wK", "."], [".", "bK"]])
    runner.run(["print board"])
    assert stdout.getvalue().splitlines() == ["wK .", ". bK"]


def test_print_without_board_argument_prints_nothing():
    board, runner, stdout = make_runner([["wK"]])
    runner.run(["print something_else"])
    assert stdout.getvalue() == ""


def test_unknown_command_is_ignored():
    board, runner, stdout = make_runner([["wK"]])
    runner.run(["fly 1 2"])
    assert stdout.getvalue() == ""


def test_promote_command_is_dispatched_to_the_game():
    rows = [[".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    board, runner, stdout = make_runner(rows)
    runner.run(["click 150 150", "promote R", "click 150 50", "wait 1000"])
    assert board.get_cell(0, 1).token == "wR"


def test_invalid_promote_command_raises_validation_error():
    board, runner, stdout = make_runner([["wP"]])
    with pytest.raises(InvalidPromotionTypeError):
        runner.run(["promote K"])


def test_full_command_sequence_end_to_end():
    board, runner, stdout = make_runner([["wK", "bQ"]])
    runner.run(
        [
            "click 50 50",
            "wait 100",
            "click 150 50",
            "wait 1000",
            "print board",
        ]
    )
    assert stdout.getvalue().splitlines() == [". wK"]
