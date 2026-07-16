WHITE_PLAYER_NAME = "White Player"
BLACK_PLAYER_NAME = "Black Player"


class PlayerPanel:
    def __init__(
        self,
        white_player_name: str = WHITE_PLAYER_NAME,
        black_player_name: str = BLACK_PLAYER_NAME,
    ) -> None:
        self.white_player_name = white_player_name
        self.black_player_name = black_player_name

    def status_text(self, snapshot, active_moves: list[dict]) -> str:
        if snapshot.game_over:
            status = "Game Over"
        elif snapshot.selected is not None:
            row, col = snapshot.selected
            status = f"Selected: ({row}, {col})"
        elif active_moves:
            status = f"Active moves: {len(active_moves)}"
        else:
            status = "Ready"

        return f"{self.white_player_name} vs {self.black_player_name} | {status}"

    def side_panel_lines(
        self,
        snapshot,
        white_moves: list[str],
        black_moves: list[str],
    ) -> tuple[list[str], list[str]]:
        white_score = snapshot.score_by_color.get("w", 0)
        black_score = snapshot.score_by_color.get("b", 0)

        return (
    [
        self.white_player_name,
        f"Score: {white_score}",
        "Moves:",
        *white_moves[1:],
    ],
    [
        self.black_player_name,
        f"Score: {black_score}",
        "Moves:",
        *black_moves[1:],
    ],
)