import io

import pytest

from kongfu_chess.errors import UnknownTokenError
from main import main, run


VALID_INPUT = "Board:\nwK .\n. bK\nCommands:\n"


def test_run_returns_board_for_valid_input():
    board = run(VALID_INPUT)
    assert board.num_rows == 2
    assert board.num_cols == 2


def test_run_propagates_parsing_errors():
    with pytest.raises(UnknownTokenError):
        run("Board:\nzz\nCommands:\n")


def test_main_prints_canonical_board_for_valid_input():
    stdin = io.StringIO(VALID_INPUT)
    stdout = io.StringIO()

    main(stdin=stdin, stdout=stdout)

    assert stdout.getvalue().splitlines() == ["wK .", ". bK"]


def test_main_normalizes_irregular_spacing_in_the_input():
    stdin = io.StringIO("Board:\nwK    .\n.   bK\nCommands:\n")
    stdout = io.StringIO()

    main(stdin=stdin, stdout=stdout)

    assert stdout.getvalue().splitlines() == ["wK .", ". bK"]


def test_main_prints_error_and_exits_nonzero_for_invalid_input():
    stdin = io.StringIO("Board:\nzz\nCommands:\n")
    stdout = io.StringIO()

    with pytest.raises(SystemExit) as excinfo:
        main(stdin=stdin, stdout=stdout)

    assert excinfo.value.code == 1
    assert stdout.getvalue().strip() == "ERROR UNKNOWN_TOKEN"
