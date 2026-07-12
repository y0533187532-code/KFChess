"""Negative / invalid move stability tests (DOCX Iteration 8).

Each case documents which layer owns the rejection:
- Controller: selection policy, out-of-bounds clicks
- GameEngine: game_over, route_conflict; delegates rule checks to RuleEngine
- RuleEngine: outside_board, empty_source, friendly_destination,
  illegal_piece_move, path_blocked
"""

from kongfu_chess.engine.types import MoveResult
from kongfu_chess.game import Game
from kongfu_chess.model.board import Board
from kongfu_chess.rules import RuleEngine

STABLE_RULE_REASONS = frozenset(
    {
        "ok",
        "outside_board",
        "empty_source",
        "friendly_destination",
        "illegal_piece_move",
        "path_blocked",
    }
)
STABLE_ENGINE_REASONS = frozenset({"ok", "game_over", "route_conflict"})


def make_game(rows):
    board = Board(rows)
    return board, Game(board)


def test_blocked_rook_slide_leaves_board_unchanged_after_wait():
    """RuleEngine — blocked path; no motion started; wait does not mutate board."""
    board, game = make_game([["wR", "wP", "."], [".", ".", "."], [".", ".", "bK"]])
    before = board.render_rows()
    game.handle_click(50, 50)
    game.handle_click(250, 50)
    assert game._selected is None
    assert game._active_moves == []
    game.handle_wait(3000)
    assert board.render_rows() == before


def test_friendly_reselect_via_click_leaves_board_unchanged():
    """Controller — clicking another friendly piece reselects; no move scheduled."""
    board, game = make_game([["wR", "wP", "."]])
    before = board.render_rows()
    game.handle_click(50, 50)
    game.handle_click(150, 50)
    assert game._selected == (0, 1)
    assert board.render_rows() == before
    assert game._active_moves == []


def test_illegal_shape_leaves_board_unchanged():
    board, game = make_game([["wR", ".", "."], [".", ".", "."], [".", ".", "."]])
    before = board.render_rows()
    game.handle_click(50, 50)
    game.handle_click(150, 150)
    assert board.render_rows() == before
    assert game._active_moves == []


def test_game_engine_returns_stable_rule_reason_for_blocked_slide():
    board = Board([["wR", "wP", "."]])
    engine = Game(board, rule_engine=RuleEngine()).engine
    result = engine.request_move(0, 0, 0, 2)
    assert result.is_accepted is False
    assert result.reason in STABLE_RULE_REASONS
    assert result.reason == "path_blocked"
    assert engine.active_moves == []


def test_game_engine_returns_stable_reason_for_friendly_block():
    board = Board([["wR", "wP", "."]])
    engine = Game(board, rule_engine=RuleEngine()).engine
    result = engine.request_move(0, 0, 0, 1)
    assert result == MoveResult(is_accepted=False, reason="friendly_destination")
    assert result.reason in STABLE_RULE_REASONS


def test_game_engine_game_over_reason_is_stable():
    board = Board([["wR", "bK"]])
    game = Game(board)
    game.engine.request_move(0, 0, 0, 1)
    game.handle_wait(1000)
    result = game.engine.request_move(0, 1, 0, 0)
    assert result.reason == "game_over"
    assert result.reason in STABLE_ENGINE_REASONS


def test_rule_engine_reasons_are_stable_set():
    board = Board([["wR", "wP", "."]])
    engine = RuleEngine()
    cases = [
        (0, 0, 0, 2, "path_blocked"),
        (0, 0, 0, 1, "friendly_destination"),
        (0, 0, 5, 0, "outside_board"),
    ]
    for from_row, from_col, to_row, to_col, expected in cases:
        result = engine.validate_move(board, from_row, from_col, to_row, to_col)
        assert result.reason in STABLE_RULE_REASONS
        assert result.reason == expected

    diagonal_board = Board([["wR", ".", "."], [".", ".", "."], [".", ".", "."]])
    assert (
        engine.validate_move(diagonal_board, 0, 0, 2, 2).reason == "illegal_piece_move"
    )
