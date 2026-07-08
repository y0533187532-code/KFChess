import io

import pytest

from kongfu_chess.errors import UnknownTokenError
from main import main, run


VALID_INPUT = "Board:\nwK .\n. bK\nCommands:\n"


def test_run_returns_board_for_valid_input():
    board = run(VALID_INPUT, io.StringIO())
    assert board.num_rows == 2
    assert board.num_cols == 2


def test_run_propagates_parsing_errors():
    with pytest.raises(UnknownTokenError):
        run("Board:\nzz\nCommands:\n", io.StringIO())


def test_run_replays_click_commands_from_the_commands_section():
    raw_text = (
        "Board:\nwK .\n. bK\nCommands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "print board\n"
    )
    stdout = io.StringIO()
    board = run(raw_text, stdout)

    assert board.render_rows() == [". .", ". wK"]
    assert stdout.getvalue().splitlines() == [". .", ". wK"]


def test_main_only_prints_when_a_print_board_command_is_given():
    # Iteration 2 makes output explicit via the "print board" command,
    # rather than always dumping the board at the end.
    stdin = io.StringIO(VALID_INPUT)
    stdout = io.StringIO()

    main(stdin=stdin, stdout=stdout)

    assert stdout.getvalue() == ""


def test_main_prints_canonical_board_on_explicit_print_command():
    stdin = io.StringIO("Board:\nwK .\n. bK\nCommands:\nprint board\n")
    stdout = io.StringIO()

    main(stdin=stdin, stdout=stdout)

    assert stdout.getvalue().splitlines() == ["wK .", ". bK"]


def test_main_normalizes_irregular_spacing_in_the_input():
    stdin = io.StringIO("Board:\nwK    .\n.   bK\nCommands:\nprint board\n")
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
