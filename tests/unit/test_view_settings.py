import pytest

from kongfu_chess.graphics.view_settings import ViewSettings


def test_view_settings_copies_and_protects_mappings():
    player_names = {"r": "Red", "g": "Green"}
    settings = ViewSettings(player_names=player_names)

    player_names["r"] = "Changed"

    assert settings.player_names["r"] == "Red"
    with pytest.raises(TypeError):
        settings.player_names["r"] = "Changed"


def test_view_settings_requires_two_players_for_current_layout():
    with pytest.raises(ValueError, match="requires two players"):
        ViewSettings(player_names={"r": "Red"})


def test_view_settings_requires_positive_log_limit():
    with pytest.raises(ValueError, match="must be positive"):
        ViewSettings(max_move_log_lines=0)
