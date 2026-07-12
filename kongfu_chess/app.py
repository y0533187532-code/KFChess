"""Application entry: parse input, run commands, return the resulting Board."""

from .errors import BoardParsingError, InvalidPromotionTypeError, MissingPromotionChoiceError
from .game import Game
from .io.board_parser import BoardParser
from .texttests.script_parser import InputParser
from .texttests.script_runner import ScriptRunner


def run(raw_text, stdout, input_parser=None, board_parser=None):
    """Parse raw_text, replay its commands, and return the resulting Board.

    Raises BoardParsingError (see kongfu_chess.errors) on any invalid input.
    """
    parser = input_parser or InputParser()
    board_parser = board_parser or BoardParser(parser)
    board_rows, command_lines = parser.parse(raw_text)

    board = board_parser.parse_rows(board_rows)
    game = Game(board)
    ScriptRunner(game, board, stdout).run(command_lines)

    return board


__all__ = ["BoardParsingError", "InvalidPromotionTypeError", "MissingPromotionChoiceError", "run"]
