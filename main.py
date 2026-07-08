"""Kong-Fu-Chess - Iteration 1: board & piece parsing.

Git repo: <TODO: put the repo URL here>

`main()` only wires stdin -> `run()` -> stdout together (single
responsibility: orchestration). All the actual logic lives in the
`kongfu_chess` package and is unit-tested there directly, and `run()`
takes the raw text as a parameter (dependency injection) so tests can
call it with any string, with no need to monkeypatch sys.stdin.
"""

import sys

from kongfu_chess.board import Board
from kongfu_chess.errors import BoardParsingError
from kongfu_chess.parser import InputParser


def run(raw_text, input_parser=None):
    """Parse raw_text and return a validated Board.

    Raises BoardParsingError (see kongfu_chess.errors) on any invalid input.
    """
    parser = input_parser or InputParser()
    board_rows, _command_lines = parser.parse(raw_text)
    return Board(board_rows)


def main(stdin=None, stdout=None):
    """CLI entry point.

    stdin/stdout default to the real sys.stdin/sys.stdout, but can be
    replaced by the caller (e.g. an io.StringIO in tests). This is plain
    dependency injection - it lets tests exercise main() end-to-end with
    no need to monkeypatch sys.stdin/sys.stdout.
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    raw_text = stdin.read()
    try:
        board = run(raw_text)
    except BoardParsingError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)

    for line in board.render_rows():
        print(line, file=stdout)


if __name__ == "__main__":  # pragma: no cover
    main()
