from ..view_settings import DEFAULT_PLAYER_NAMES, ViewSettings


_DEFAULT_PLAYER_COLORS = tuple(DEFAULT_PLAYER_NAMES)
WHITE_PLAYER_NAME = DEFAULT_PLAYER_NAMES[_DEFAULT_PLAYER_COLORS[0]]
BLACK_PLAYER_NAME = DEFAULT_PLAYER_NAMES[_DEFAULT_PLAYER_COLORS[1]]


class PlayerPanel:
    def __init__(self, settings: ViewSettings | None = None) -> None:
        self._settings = ViewSettings() if settings is None else settings

    def status_text(self, snapshot) -> str:
        if snapshot.game_over:
            status = "Game Over"
        elif snapshot.selected is not None:
            row, col = snapshot.selected
            status = f"Selected: ({row}, {col})"
        elif snapshot.active_motions:
            status = f"Active moves: {len(snapshot.active_motions)}"
        else:
            status = "Ready"

        player_names = tuple(self._settings.player_names.values())
        return f"{' vs '.join(player_names)} | {status}"

    def side_panel_lines(
        self,
        snapshot,
        first_player_moves: list[str],
        second_player_moves: list[str],
    ) -> tuple[list[str], list[str]]:
        first_color, second_color = self._settings.player_colors
        first_name = self._settings.player_names[first_color]
        second_name = self._settings.player_names[second_color]
        first_score = snapshot.score_by_color.get(first_color, 0)
        second_score = snapshot.score_by_color.get(second_color, 0)

        return (
            [
                first_name,
                f"{self._settings.score_label}: {first_score}",
                f"{self._settings.moves_label}:",
                *first_player_moves[1:],
            ],
            [
                second_name,
                f"{self._settings.score_label}: {second_score}",
                f"{self._settings.moves_label}:",
                *second_player_moves[1:],
            ],
        )
