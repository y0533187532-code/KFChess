"""Explicit coverage for requirements in kung_fu_chess_en.docx / _spec.zip."""

from dataclasses import FrozenInstanceError

import pytest

from kongfu_chess.config import CELL_SIZE_PX, DEFAULT_MOVE_DURATION_MS
from kongfu_chess.engine.types import GameSnapshot, PieceSnapshot
from kongfu_chess.model.board import Board
from kongfu_chess.rules import RuleEngine
from kongfu_chess.view.renderer import Renderer


def test_design_guide_timing_and_pixel_constants():
    assert CELL_SIZE_PX == 100
    assert all(duration == 500 for duration in DEFAULT_MOVE_DURATION_MS.values())


def test_rule_engine_validate_move_is_read_only():
    board = Board([["wR", "wP", "."]])
    before = board.render_rows()
    result = RuleEngine().validate_move(board, 0, 0, 0, 2)
    assert result.is_valid is False
    assert board.render_rows() == before


def test_game_snapshot_is_immutable_read_only_dto():
    snapshot = GameSnapshot(
        board_width=2,
        board_height=1,
        game_over=False,
        selected=(0, 0),
        pieces=(PieceSnapshot(row=0, col=0, token="wK", piece_id=0),),
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.game_over = True


def test_renderer_derives_logical_rows_without_mutating_snapshot():
    snapshot = GameSnapshot(
        board_width=2,
        board_height=1,
        game_over=False,
        pieces=(PieceSnapshot(row=0, col=1, token="wK", piece_id=0),),
    )
    rows = Renderer().render_logical_rows(snapshot)
    assert rows == [". wK"]
    assert snapshot.pieces[0].token == "wK"
