from kongfu_chess.piece import Piece


def test_from_token_builds_piece_with_color_and_type():
    piece = Piece.from_token("wP")
    assert piece.color == "w"
    assert piece.piece_type == "P"


def test_from_token_returns_none_for_wrong_length():
    assert Piece.from_token("w") is None
    assert Piece.from_token("wPP") is None
    assert Piece.from_token("") is None


def test_is_valid_true_for_known_color_and_type():
    piece = Piece.from_token("bK")
    assert piece.is_valid(valid_colors={"b", "w"}, valid_piece_types={"K", "Q"}) is True


def test_is_valid_false_for_unknown_color():
    piece = Piece.from_token("xK")
    assert piece.is_valid(valid_colors={"b", "w"}, valid_piece_types={"K"}) is False


def test_is_valid_false_for_unknown_piece_type():
    piece = Piece.from_token("wZ")
    assert piece.is_valid(valid_colors={"b", "w"}, valid_piece_types={"K"}) is False


def test_piece_supports_custom_rule_sets_not_just_standard_chess():
    # A "design your own game" rule-set could define entirely different
    # colors/types; Piece must not assume the standard chess set.
    drone = Piece.from_token("gD")
    assert drone.is_valid(valid_colors={"g", "r"}, valid_piece_types={"D"}) is True


def test_token_reconstructs_canonical_two_character_form():
    piece = Piece.from_token("wP")
    assert piece.token == "wP"
