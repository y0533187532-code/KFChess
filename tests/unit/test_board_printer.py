import io

from kongfu_chess.io.board_printer import BoardPrinter
from kongfu_chess.model.board import Board


def test_render_rows_matches_board_render_rows():
    board = Board([["wK", "."]])
    assert BoardPrinter().render_rows(board) == ["wK ."]


def test_print_writes_canonical_rows_to_stdout():
    board = Board([["wK", "."], [".", "bK"]])
    stdout = io.StringIO()
    BoardPrinter().print(board, stdout)
    assert stdout.getvalue().splitlines() == ["wK .", ". bK"]
