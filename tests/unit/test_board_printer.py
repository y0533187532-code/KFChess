import io

from kongfu_chess.engine.types import GameSnapshot, PieceSnapshot
from kongfu_chess.game import Game
from kongfu_chess.io.board_printer import BoardPrinter
from kongfu_chess.model.board import Board
from kongfu_chess.model.piece import PIECE_STATE_CAPTURED


def test_render_rows_matches_board_render_rows():
    board = Board([["wK", "."]])
    assert BoardPrinter().render_rows(board) == ["wK ."]


def test_render_rows_accepts_game_snapshot():
    board = Board([["wK", "."], [".", "bK"]])
    snapshot = Game(board).snapshot()
    assert BoardPrinter().render_rows(snapshot) == ["wK .", ". bK"]


def test_print_writes_canonical_rows_to_stdout():
    board = Board([["wK", "."], [".", "bK"]])
    stdout = io.StringIO()
    BoardPrinter().print(board, stdout)
    assert stdout.getvalue().splitlines() == ["wK .", ". bK"]


def test_render_rows_from_snapshot_omits_captured_pieces():
    snapshot = GameSnapshot(
        board_width=2,
        board_height=1,
        game_over=False,
        pieces=(
            PieceSnapshot(row=0, col=0, token="wR", piece_id=0, state="idle"),
            PieceSnapshot(row=0, col=1, token="bQ", piece_id=1, state=PIECE_STATE_CAPTURED),
        ),
    )
    assert BoardPrinter().render_rows(snapshot) == ["wR ."]
