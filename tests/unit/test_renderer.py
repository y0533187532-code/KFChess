import io

from kongfu_chess.engine.types import PieceSnapshot
from kongfu_chess.game import Game
from kongfu_chess.io.board_printer import BoardPrinter
from kongfu_chess.model.board import Board
from kongfu_chess.view.renderer import Renderer


def test_renderer_logical_rows_match_board_printer():
    board = Board([["wK", "."], [".", "bK"]])
    game = Game(board)
    snapshot = game.snapshot()
    assert Renderer().render_logical_rows(snapshot) == BoardPrinter().render_rows(board)


def test_renderer_render_writes_rows_without_mutating_game():
    board = Board([["wK", "."]])
    game = Game(board)
    before = board.render_rows()
    snapshot = game.snapshot()
    stdout = io.StringIO()
    rows = Renderer().render(snapshot, stdout=stdout)
    assert rows == ["wK ."]
    assert stdout.getvalue().splitlines() == ["wK ."]
    assert board.render_rows() == before
    assert game.snapshot().pieces == snapshot.pieces


def test_snapshot_pieces_are_piece_snapshot_dtos():
    board = Board([["wK"]])
    game = Game(board)
    snapshot = game.snapshot()
    assert len(snapshot.pieces) == 1
    piece = snapshot.pieces[0]
    assert isinstance(piece, PieceSnapshot)
    assert piece.row == 0
    assert piece.col == 0
    assert piece.token == "wK"


def test_renderer_cell_center_pixels_use_board_mapper_geometry():
    renderer = Renderer()
    assert renderer.cell_center_pixels(0, 0) == (50, 50)
    assert renderer.cell_center_pixels(1, 2) == (250, 150)
