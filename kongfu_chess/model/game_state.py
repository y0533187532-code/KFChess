"""Read-only game-state container for future engine/rendering layers."""

from dataclasses import dataclass

from .board import Board


@dataclass
class GameState:
    board: Board
    game_over: bool = False
    selected: tuple | None = None

    @property
    def is_game_over(self):
        return self.game_over
