import pytest

from kongfu_chess.model.board import Board
from kongfu_chess.rules import (
    PieceRules,
    RuleEngine,
    get_move_route,
    is_bishop_move,
    is_king_move,
    is_knight_move,
    is_path_clear,
    is_pawn_move,
    is_promotion_row,
    is_queen_move,
    is_route_conflict,
    is_rook_move,
    is_swap_route,
    pawn_start_row,
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


def test_piece_rules_uses_default_rules_for_known_piece_types():
    rules = PieceRules()
    assert rules.is_legal_shape("K", 1, 0) is True
    assert rules.is_legal_shape("K", 2, 0) is False


def test_piece_rules_returns_false_for_unregistered_piece_type():
    rules = PieceRules()
    assert rules.is_legal_shape("X", 1, 0) is False


def test_piece_rules_supports_registering_a_custom_piece_type():
    rules = PieceRules()
    rules.register("D", lambda dr, dc: max(abs(dr), abs(dc)) <= 2)
    assert rules.is_legal_shape("D", 2, 2) is True
    assert rules.is_legal_shape("D", 3, 0) is False


def test_piece_rules_can_be_constructed_with_a_fully_custom_rule_set():
    custom_rules = PieceRules(shape_rules={"X": lambda dr, dc: True})
    assert custom_rules.is_legal_shape("X", 5, 5) is True
    assert custom_rules.is_legal_shape("K", 1, 0) is False


def test_rook_bishop_queen_require_clear_path_by_default():
    rules = PieceRules()
    assert rules.requires_clear_path("R") is True
    assert rules.requires_clear_path("B") is True
    assert rules.requires_clear_path("Q") is True


def test_knight_and_king_do_not_require_clear_path_by_default():
    rules = PieceRules()
    assert rules.requires_clear_path("N") is False
    assert rules.requires_clear_path("K") is False


def test_register_can_mark_a_custom_piece_type_as_sliding():
    rules = PieceRules()
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


# --- Pawn movement rules ---

def test_white_pawn_moves_forward_one_cell_to_empty():
    assert is_pawn_move(-1, 0, "w", None) is True


def test_black_pawn_moves_forward_one_cell_to_empty():
    assert is_pawn_move(1, 0, "b", None) is True


def test_white_pawn_cannot_move_backward():
    assert is_pawn_move(1, 0, "w", None) is False


def test_black_pawn_cannot_move_backward():
    assert is_pawn_move(-1, 0, "b", None) is False


def test_white_pawn_cannot_move_two_cells_without_board_context():
    assert is_pawn_move(-2, 0, "w", None) is False


def test_white_pawn_double_step_from_start_row_with_clear_path():
    board = Board([[".", "."], [".", "."], [".", "wP"]])
    assert is_pawn_move(
        -2, 0, "w", None, board=board, from_row=2, from_col=1, to_col=1
    ) is True


def test_white_pawn_double_step_rejected_when_not_on_start_row():
    board = Board([[".", "."], [".", "wP"], [".", "."]])
    assert is_pawn_move(
        -2, 0, "w", None, board=board, from_row=1, from_col=1, to_col=1
    ) is False


def test_white_pawn_double_step_rejected_when_intermediate_blocked():
    board = Board([[".", "."], [".", "bN"], [".", "wP"]])
    assert is_pawn_move(
        -2, 0, "w", None, board=board, from_row=2, from_col=1, to_col=1
    ) is False


def test_white_pawn_double_step_rejected_when_destination_occupied():
    from kongfu_chess.model.piece import Piece
    blocker = Piece(color="b", piece_type="N")
    board = Board([[".", "bN"], [".", "."], [".", "wP"]])
    assert is_pawn_move(
        -2, 0, "w", blocker, board=board, from_row=2, from_col=1, to_col=1
    ) is False


def test_pawn_start_row_and_promotion_row():
    assert pawn_start_row("w", 3) == 2
    assert pawn_start_row("b", 3) == 0
    assert is_promotion_row(0, 3) is True
    assert is_promotion_row(2, 3) is True
    assert is_promotion_row(1, 3) is False


def test_pawn_forward_direction_is_injectable_via_piece_rules():
    rules = PieceRules(pawn_forward_by_color={"w": 1, "b": -1})
    assert rules.is_legal_shape("P", 1, 0, color="w", target_piece=None) is True
    assert rules.is_legal_shape("P", -1, 0, color="w", target_piece=None) is False


def test_pawn_cannot_move_forward_to_occupied_cell():
    from kongfu_chess.model.piece import Piece
    blocker = Piece(color="b", piece_type="P")
    assert is_pawn_move(-1, 0, "w", blocker) is False


def test_white_pawn_captures_diagonally_forward():
    from kongfu_chess.model.piece import Piece
    enemy = Piece(color="b", piece_type="N")
    assert is_pawn_move(-1, 1, "w", enemy) is True
    assert is_pawn_move(-1, -1, "w", enemy) is True


def test_black_pawn_captures_diagonally_forward():
    from kongfu_chess.model.piece import Piece
    enemy = Piece(color="w", piece_type="N")
    assert is_pawn_move(1, 1, "b", enemy) is True
    assert is_pawn_move(1, -1, "b", enemy) is True


def test_pawn_cannot_capture_forward_without_diagonal():
    from kongfu_chess.model.piece import Piece
    enemy = Piece(color="b", piece_type="N")
    assert is_pawn_move(-1, 0, "w", enemy) is False


def test_pawn_cannot_capture_own_color_diagonally():
    from kongfu_chess.model.piece import Piece
    friendly = Piece(color="w", piece_type="N")
    assert is_pawn_move(-1, 1, "w", friendly) is False


def test_piece_rules_is_legal_shape_delegates_to_pawn_correctly():
    from kongfu_chess.model.piece import Piece
    rules = PieceRules()
    enemy = Piece(color="b", piece_type="P")
    board = Board([[".", "."], [".", "."], [".", "wP"]])
    assert rules.is_legal_shape("P", -1, 0, color="w", target_piece=None) is True
    assert rules.is_legal_shape("P", -1, 1, color="w", target_piece=enemy) is True
    assert rules.is_legal_shape("P", -2, 0, color="w", target_piece=None) is False
    assert rules.is_legal_shape(
        "P",
        -2,
        0,
        color="w",
        target_piece=None,
        board=board,
        from_row=2,
        from_col=1,
        to_row=0,
        to_col=1,
    ) is True


# --- Move route and conflict detection ---

def test_get_move_route_for_rook_includes_intermediate_cells():
    assert get_move_route(0, 0, 0, 3, "R") == [(0, 1), (0, 2), (0, 3)]


def test_get_move_route_for_knight_is_destination_only():
    assert get_move_route(0, 0, 1, 2, "N") == [(1, 2)]


def test_get_move_route_for_pawn_double_step_includes_intermediate():
    assert get_move_route(2, 1, 0, 1, "P") == [(1, 1), (0, 1)]


def test_get_move_route_for_pawn_single_step_is_destination_only():
    assert get_move_route(1, 1, 0, 1, "P") == [(0, 1)]


def test_is_swap_route_true_for_enemy_swapping_endpoints():
    assert is_swap_route((0, 0), (0, 2), "w", (0, 2), (0, 0), "b") is True


def test_is_swap_route_false_for_same_color():
    assert is_swap_route((0, 0), (0, 1), "w", (0, 1), (0, 0), "w") is False


def test_is_route_conflict_when_routes_overlap():
    existing_route = [(0, 1), (0, 2)]
    new_route = [(0, 2), (0, 3)]
    assert is_route_conflict(
        (0, 0), (0, 2), existing_route,
        (0, 4), (0, 2), new_route,
        "w", "b",
    ) is True


def test_is_route_conflict_when_landing_on_active_origin():
    assert is_route_conflict(
        (0, 0), (0, 2), [(0, 1), (0, 2)],
        (0, 4), (0, 0), [(0, 0)],
        "w", "b",
    ) is True


def test_is_route_conflict_false_for_enemy_swap():
    assert is_route_conflict(
        (0, 0), (0, 2), [(0, 1), (0, 2)],
        (0, 2), (0, 0), [(0, 1), (0, 0)],
        "w", "b",
    ) is False


def test_is_route_conflict_false_when_either_move_is_a_jump():
    assert is_route_conflict(
        (0, 0), (0, 0), [],
        (0, 4), (0, 0), [(0, 0)],
        "w", "b",
        existing_jump=True,
    ) is False
    assert is_route_conflict(
        (0, 0), (0, 2), [(0, 1), (0, 2)],
        (0, 4), (0, 0), [(0, 0)],
        "w", "b",
        new_jump=True,
    ) is False


def test_is_route_conflict_when_opposite_colors_share_a_column_on_parallel_rows():
    assert is_route_conflict(
        (0, 0), (0, 2), [(0, 1), (0, 2)],
        (2, 0), (2, 2), [(2, 1), (2, 2)],
        "w", "b",
    ) is True


def test_is_route_conflict_false_for_opposite_colors_on_same_row_adjacent():
    assert is_route_conflict(
        (0, 0), (0, 1), [(0, 1)],
        (0, 3), (0, 2), [(0, 2)],
        "w", "b",
    ) is False


def test_is_route_conflict_false_for_same_color_parallel_routes():
    assert is_route_conflict(
        (0, 0), (0, 2), [(0, 1), (0, 2)],
        (2, 0), (2, 2), [(2, 1), (2, 2)],
        "w", "w",
    ) is False
