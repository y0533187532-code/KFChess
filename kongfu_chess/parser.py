"""Splits the raw input protocol text into its Board and Commands sections.

The section headers are constructor parameters (defaulting to the values
in config.py) rather than literals inline in the parsing logic, so the
same parser could serve a slightly different protocol variant if ever
needed, without editing this class.

Note: the Commands section itself is not parsed/validated yet - that is
future work (see requirements section on move commands). This class only
hands the raw command lines back to the caller so that future iterations
can add command parsing without reworking how sections are split.
"""

from .config import BOARD_SECTION_HEADER, COMMANDS_SECTION_HEADER
from .errors import MissingSectionError


class InputParser:
    def __init__(
        self,
        board_header=BOARD_SECTION_HEADER,
        commands_header=COMMANDS_SECTION_HEADER,
    ):
        self._board_header = board_header
        self._commands_header = commands_header

    def parse(self, raw_text):
        """Return (board_rows, command_lines) parsed from raw_text.

        board_rows is a list of lists of tokens (one list per board row).
        command_lines is the untouched list of lines found after the
        commands header (not parsed further yet).
        """
        lines = raw_text.splitlines()
        board_index = self._find_header_index(lines, self._board_header)
        commands_index = self._find_header_index(lines, self._commands_header)

        board_lines = lines[board_index + 1 : commands_index]
        command_lines = lines[commands_index + 1 :]

        board_rows = [line.split() for line in board_lines]
        return board_rows, command_lines

    def _find_header_index(self, lines, header):
        try:
            return lines.index(header)
        except ValueError:
            raise MissingSectionError(header)
