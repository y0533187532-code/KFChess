import pytest

from kongfu_chess.board import Board
from kongfu_chess.movement import (
    MovementRules,
    is_bishop_move,
    is_king_move,
    is_knight_move,
    is_path_clear,
    is_queen_move,
    is_rook_move,
)


@pytest.mark.parametrize(
    "dr, dc, expected",
    [(0, 1, True), (1, 1, True), (1, 0, True), (0, 2, False), (2, 1, False)],
)
def test_king_move(dr, dc, expected):
    assert is_king_move(dr, dc) is expected


@pytest.mark.parametrize(
    "dr, dc, expected",
    [(0, 5, True), (5, 0, True), (0, 0, False), (1, 1, False)],
)
def test_rook_move(dr, dc, expected):
    assert is_rook_move(dr, dc) is expected


@pytest.mark.parametrize(
    "dr, dc, expected",
    [(3, 3, True), (-2, 2, True), (0, 0, False), (2, 3, False)],
)
def test_bishop_move(dr, dc, expected):
    assert is_bishop_move(dr, dc) is expected


@pytest.mark.parametrize(
    "dr, dc, expected",
    [(1, 2, True), (2, 1, True), (-1, -2, True), (2, 2, False), (1, 1, False)],
)
def test_knight_move(dr, dc, expected):
    assert is_knight_move(dr, dc) is expected


@pytest.mark.parametrize(
    "dr, dc, expected",
    [(0, 4, True), (4, 4, True), (1, 2, False)],
)
def test_queen_move(dr, dc, expected):
    assert is_queen_move(dr, dc) is expected


def test_movement_rules_uses_default_rules_for_known_piece_types():
    rules = MovementRules()
    assert rules.is_legal("K", 1, 0) is True
    assert rules.is_legal("K", 2, 0) is False


def test_movement_rules_returns_false_for_unregistered_piece_type():
    # e.g. Pawn - not yet supported - must be safely "illegal", never raise.
    rules = MovementRules()
    assert rules.is_legal("P", 1, 0) is False


def test_movement_rules_supports_registering_a_custom_piece_type():
    # Future "design your own game": a brand new piece type, registered
    # without touching MovementRules or Game at all.
    rules = MovementRules()
    rules.register("D", lambda dr, dc: max(abs(dr), abs(dc)) <= 2)
    assert rules.is_legal("D", 2, 2) is True
    assert rules.is_legal("D", 3, 0) is False


def test_movement_rules_can_be_constructed_with_a_fully_custom_rule_set():
    custom_rules = MovementRules(rules={"X": lambda dr, dc: True})
    assert custom_rules.is_legal("X", 5, 5) is True
    assert custom_rules.is_legal("K", 1, 0) is False  # standard "K" not present here


def test_rook_bishop_queen_require_clear_path_by_default():
    rules = MovementRules()
    assert rules.requires_clear_path("R") is True
    assert rules.requires_clear_path("B") is True
    assert rules.requires_clear_path("Q") is True


def test_knight_and_king_do_not_require_clear_path_by_default():
    rules = MovementRules()
    assert rules.requires_clear_path("N") is False
    assert rules.requires_clear_path("K") is False


def test_register_can_mark_a_custom_piece_type_as_sliding():
    rules = MovementRules()
    rules.register("D", lambda dr, dc: True, sliding=True)
    assert rules.requires_clear_path("D") is True


def test_is_path_clear_true_when_no_blockers_between():
    board = Board([["wR", ".", ".", "."]])
    assert is_path_clear(board, 0, 0, 0, 3) is True


def test_is_path_clear_false_when_a_piece_blocks_the_way():
    board = Board([["wR", ".", "bN", "."]])
    assert is_path_clear(board, 0, 0, 0, 3) is False


def test_is_path_clear_works_diagonally():
    rows = [["wB", ".", "."], [".", ".", "."], [".", ".", "."]]
    board = Board(rows)
    assert is_path_clear(board, 0, 0, 2, 2) is True

    rows_blocked = [["wB", ".", "."], [".", "bN", "."], [".", ".", "."]]
    board_blocked = Board(rows_blocked)
    assert is_path_clear(board_blocked, 0, 0, 2, 2) is False


def test_is_path_clear_true_for_adjacent_cells_with_no_cell_between():
    board = Board([["wR", "."]])
    assert is_path_clear(board, 0, 0, 0, 1) is True
