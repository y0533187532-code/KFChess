import pytest

from kongfu_chess.errors import MissingSectionError
from kongfu_chess.parser import InputParser


def test_parses_board_and_command_lines():
    raw_text = "Board:\nwK .\n. bK\nCommands:\nNC6\n"
    board_rows, command_lines = InputParser().parse(raw_text)
    assert board_rows == [["wK", "."], [".", "bK"]]
    assert command_lines == ["NC6"]


def test_parses_empty_commands_section():
    raw_text = "Board:\nwK\nCommands:\n"
    board_rows, command_lines = InputParser().parse(raw_text)
    assert board_rows == [["wK"]]
    assert command_lines == []


def test_missing_board_header_raises_error():
    raw_text = "wK\nCommands:\n"
    with pytest.raises(MissingSectionError) as excinfo:
        InputParser().parse(raw_text)
    assert excinfo.value.header == "Board:"


def test_missing_commands_header_raises_error():
    raw_text = "Board:\nwK\n"
    with pytest.raises(MissingSectionError) as excinfo:
        InputParser().parse(raw_text)
    assert excinfo.value.header == "Commands:"


def test_custom_headers_are_honoured():
    parser = InputParser(board_header="BOARD", commands_header="MOVES")
    raw_text = "BOARD\nwK\nMOVES\nE4\n"
    board_rows, command_lines = parser.parse(raw_text)
    assert board_rows == [["wK"]]
    assert command_lines == ["E4"]


def test_parses_board_header_with_leading_whitespace():
    raw_text = " Board:\nwK .\nCommands:\n"
    board_rows, command_lines = InputParser().parse(raw_text)
    assert board_rows == [["wK", "."]]
    assert command_lines == []


def test_skips_blank_lines_in_board_section():
    raw_text = "Board:\n\nwK .\n\n. bK\nCommands:\n"
    board_rows, command_lines = InputParser().parse(raw_text)
    assert board_rows == [["wK", "."], [".", "bK"]]
    assert command_lines == []
