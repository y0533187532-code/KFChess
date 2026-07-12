import pytest

from kongfu_chess.errors import InvalidPromotionTypeError
from kongfu_chess.model.board import Board
from kongfu_chess.model.piece import Piece
from kongfu_chess.rules import (
    PieceRules,
    resolve_promotion_piece_type,
    validate_promotion_piece_type,
)
from kongfu_chess.game import Game


@pytest.fixture
def piece_rules():
    return PieceRules()


def test_allowed_promotion_types_defaults_to_shape_minus_k_and_p():
    assert PieceRules().allowed_promotion_types() == frozenset({"Q", "R", "B", "N"})


def test_validate_promotion_piece_type_accepts_queen_rook_bishop_knight(piece_rules):
    for piece_type in ("Q", "R", "B", "N"):
        assert validate_promotion_piece_type(piece_type, piece_rules) == piece_type


def test_validate_promotion_piece_type_rejects_invalid_type(piece_rules):
    with pytest.raises(InvalidPromotionTypeError) as excinfo:
        validate_promotion_piece_type("K", piece_rules)
    assert excinfo.value.piece_type == "K"
    assert excinfo.value.code == "INVALID_PROMOTION_TYPE"


def test_king_and_pawn_rejected_even_if_in_shape_rules(piece_rules):
    with pytest.raises(InvalidPromotionTypeError):
        validate_promotion_piece_type("K", piece_rules)
    with pytest.raises(InvalidPromotionTypeError):
        validate_promotion_piece_type("P", piece_rules)


def test_registered_custom_piece_is_promotable(piece_rules):
    piece_rules.register("D", lambda dr, dc: max(abs(dr), abs(dc)) <= 2)
    assert validate_promotion_piece_type("D", piece_rules) == "D"
    assert "D" in piece_rules.allowed_promotion_types()


def test_explicit_promotable_piece_types_override():
    rules = PieceRules(promotable_piece_types={"R"})
    assert rules.allowed_promotion_types() == frozenset({"R"})
    assert validate_promotion_piece_type("R", rules) == "R"
    with pytest.raises(InvalidPromotionTypeError):
        validate_promotion_piece_type("Q", rules)


def test_register_with_promotable_false_excludes_type():
    rules = PieceRules()
    rules.register("D", lambda dr, dc: True, promotable=False)
    assert "D" not in rules.allowed_promotion_types()
    with pytest.raises(InvalidPromotionTypeError):
        validate_promotion_piece_type("D", rules)


def test_resolve_promotion_defaults_to_queen_without_choice(piece_rules):
    pawn = Piece(color="w", piece_type="P", piece_id=1)
    assert resolve_promotion_piece_type(pawn, 0, 3, piece_rules) == "Q"


def test_resolve_promotion_uses_explicit_choice(piece_rules):
    pawn = Piece(color="w", piece_type="P", piece_id=1)
    assert resolve_promotion_piece_type(pawn, 0, 3, piece_rules, chosen_type="R") == "R"
    assert resolve_promotion_piece_type(pawn, 0, 3, piece_rules, chosen_type="B") == "B"
    assert resolve_promotion_piece_type(pawn, 0, 3, piece_rules, chosen_type="N") == "N"


def test_resolve_promotion_returns_none_for_non_promotion_row(piece_rules):
    pawn = Piece(color="w", piece_type="P", piece_id=1)
    assert resolve_promotion_piece_type(pawn, 1, 3, piece_rules) is None


def test_resolve_promotion_returns_none_for_non_pawn(piece_rules):
    rook = Piece(color="w", piece_type="R", piece_id=1)
    assert resolve_promotion_piece_type(rook, 0, 3, piece_rules) is None


def test_board_move_piece_preserves_piece_id_on_promotion():
    board = Board([[".", "wP"]])
    original_id = board.get_cell(0, 1).piece_id
    board.move_piece(0, 1, 0, 0, promotion_piece_type="R")
    promoted = board.get_cell(0, 0)
    assert promoted.token == "wR"
    assert promoted.piece_id == original_id


def test_registered_custom_piece_promotes_end_to_end():
    rows = [[".", ".", "."], [".", "wP", "."], [".", ".", "."]]
    board = Board(rows)
    rules = PieceRules()
    rules.register("D", lambda dr, dc: max(abs(dr), abs(dc)) <= 2)
    game = Game(board, piece_rules=rules)
    game.handle_click(150, 150)
    game.handle_promote("D")
    game.handle_click(150, 50)
    game.handle_wait(1000)
    assert board.get_cell(0, 1).token == "wD"
