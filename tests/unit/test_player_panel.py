from kongfu_chess.engine.types import GameSnapshot
from kongfu_chess.graphics.player_panel import (
    BLACK_PLAYER_NAME,
    PlayerPanel,
    WHITE_PLAYER_NAME,
)
from kongfu_chess.graphics.view_settings import ViewSettings


def test_side_panel_lines_include_player_names_and_scores():
    panel = PlayerPanel()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        score_by_color={"w": 5, "b": 9},
    )

    left_lines, right_lines = panel.side_panel_lines(
        snapshot,
        ["White", "0.0s Pawn: d2->d4"],
        ["Black"],
    )

    assert left_lines == [
        WHITE_PLAYER_NAME,
        "Score: 5",
        "Moves:",
        "0.0s Pawn: d2->d4",
    ]
    assert right_lines == [BLACK_PLAYER_NAME, "Score: 9", "Moves:"]


def test_status_text_includes_player_names():
    panel = PlayerPanel()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
    )

    status = panel.status_text(snapshot)

    assert status == f"{WHITE_PLAYER_NAME} vs {BLACK_PLAYER_NAME} | Ready"


def test_player_panel_uses_injected_colors_and_names():
    panel = PlayerPanel(
        ViewSettings(player_names={"r": "Red", "g": "Green"})
    )
    snapshot = GameSnapshot(
        board_width=3,
        board_height=3,
        game_over=False,
        score_by_color={"r": 4, "g": 7},
    )

    left_lines, right_lines = panel.side_panel_lines(
        snapshot,
        ["Red"],
        ["Green"],
    )

    assert panel.status_text(snapshot) == "Red vs Green | Ready"
    assert left_lines[:2] == ["Red", "Score: 4"]
    assert right_lines[:2] == ["Green", "Score: 7"]
