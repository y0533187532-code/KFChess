"""VPL entry point — flat imports, same behavior as repo root main.py."""

import sys

from board import Board
from commands import ScriptRunner
from errors import (
    BoardParsingError,
    InvalidPromotionTypeError,
    MissingPromotionChoiceError,
)
from game import Game
from parser import InputParser


def main(stdin=None, stdout=None):
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    raw_text = stdin.read()
    try:
        parser = InputParser()
        board_rows, command_lines = parser.parse(raw_text)
        board = Board(board_rows)
        game = Game(board)
        ScriptRunner(game, board, stdout).run(command_lines)
    except BoardParsingError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)
    except InvalidPromotionTypeError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)
    except MissingPromotionChoiceError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
