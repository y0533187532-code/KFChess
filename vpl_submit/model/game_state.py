"""Game state owned by the engine layer."""

from dataclasses import dataclass, field

try:
    from .board import Board
except ImportError:
    from board import Board


@dataclass
class GameState:
    board: Board
    game_over: bool = False
    selected: tuple | None = field(default=None)

    @property
    def is_game_over(self):
        return self.game_over

    def mark_game_over(self):
        self.game_over = True

    def clear_selection(self):
        self.selected = None

    def select(self, row, col):
        self.selected = (row, col)
