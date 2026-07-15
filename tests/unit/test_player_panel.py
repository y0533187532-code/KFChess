from kongfu_chess.engine.types import GameSnapshot
from kongfu_chess.graphics.player_panel import (
    BLACK_PLAYER_NAME,
    PlayerPanel,
    WHITE_PLAYER_NAME,
)


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
        "0.0s Pawn: d2->d4",
    ]
    assert right_lines == [BLACK_PLAYER_NAME, "Score: 9"]


def test_status_text_includes_player_names():
    panel = PlayerPanel()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
    )

    status = panel.status_text(snapshot, active_moves=[])

    assert status == f"{WHITE_PLAYER_NAME} vs {BLACK_PLAYER_NAME} | Ready"
