"""Build a Board from the textual board section of the input protocol."""

from ..model.board import Board
from ..texttests.script_parser import InputParser


class BoardParser:
    def __init__(self, input_parser=None):
        self._input_parser = input_parser or InputParser()

    def parse(self, raw_text):
        """Return a Board parsed from raw_text."""
        board_rows, _command_lines = self._input_parser.parse(raw_text)
        return Board(board_rows)

    def parse_rows(self, board_rows):
        """Return a Board from pre-split row tokens."""
        return Board(board_rows)
