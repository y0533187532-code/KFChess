"""Splits the raw input protocol text into its Board and Commands sections."""

try:
    from ..config import BOARD_SECTION_HEADER, COMMANDS_SECTION_HEADER
    from ..errors import MissingSectionError
except ImportError:
    from config import BOARD_SECTION_HEADER, COMMANDS_SECTION_HEADER
    from errors import MissingSectionError


class InputParser:
    def __init__(
        self,
        board_header=BOARD_SECTION_HEADER,
        commands_header=COMMANDS_SECTION_HEADER,
    ):
        self._board_header = board_header
        self._commands_header = commands_header

    def parse(self, raw_text):
        """Return (board_rows, command_lines) parsed from raw_text."""
        lines = raw_text.splitlines()
        board_index = self._find_header_index(lines, self._board_header)
        commands_index = self._find_header_index(lines, self._commands_header)

        board_lines = lines[board_index + 1 : commands_index]
        command_lines = lines[commands_index + 1 :]

        board_rows = [line.split() for line in board_lines if line.strip()]
        return board_rows, command_lines

    def _find_header_index(self, lines, header):
        for index, line in enumerate(lines):
            if line.strip() == header:
                return index
        raise MissingSectionError(header)


# class ScriptParser(InputParser):
#     """Alias for the text integration DSL parser (DOCX ``ScriptParser``)."""
