"""Dispatches parsed command lines to a Game, and prints board snapshots.

This is deliberately separate from Game (SRP): Game only knows about
click/wait game-state transitions, with no idea that its input ever came
from text lines at all. CommandRunner is the only place that knows the
*text* shape of "click x y" / "wait ms" / "print board" - if the protocol
ever changes (e.g. a binary/network protocol instead of text lines), only
this class needs to change.
"""

from .config import (
    CLICK_COMMAND,
    JUMP_COMMAND,
    PRINT_COMMAND,
    PRINT_BOARD_ARGUMENT,
    WAIT_COMMAND,
)


class CommandRunner:
    def __init__(self, game, board, stdout):
        self._game = game
        self._board = board
        self._stdout = stdout

    def run(self, command_lines):
        for line in command_lines:
            self._run_line(line)

    def _run_line(self, line):
        parts = line.split()
        if not parts:
            return

        command, arguments = parts[0], parts[1:]

        if command == CLICK_COMMAND:
            self._run_click(arguments)
        elif command == JUMP_COMMAND:
            self._run_jump(arguments)
        elif command == WAIT_COMMAND:
            self._run_wait(arguments)
        elif command == PRINT_COMMAND:
            self._run_print(arguments)

    def _run_click(self, arguments):
        pixel_x, pixel_y = int(arguments[0]), int(arguments[1])
        self._game.handle_click(pixel_x, pixel_y)

    def _run_jump(self, arguments):
        pixel_x, pixel_y = int(arguments[0]), int(arguments[1])
        self._game.handle_click(pixel_x, pixel_y)
        self._game.handle_click(pixel_x, pixel_y)

    def _run_wait(self, arguments):
        milliseconds = int(arguments[0])
        self._game.handle_wait(milliseconds)

    def _run_print(self, arguments):
        if arguments and arguments[0] == PRINT_BOARD_ARGUMENT:
            for row in self._board.render_rows():
                print(row, file=self._stdout)
