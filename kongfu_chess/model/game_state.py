"""Game state owned by the engine layer."""

from __future__ import annotations

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
    promotion_choice: str | None = field(default=None)
    captured_pieces: list = field(default_factory=list)
    score_by_color: dict[str, int] = field(default_factory=lambda: {"w": 0, "b": 0})
    completed_moves: list = field(default_factory=list)

    @property
    def is_game_over(self):
        return self.game_over

    def mark_game_over(self):
        self.game_over = True

    def clear_selection(self):
        self.selected = None

    def set_promotion_choice(self, piece_type):
        self.promotion_choice = piece_type

    def consume_promotion_choice(self):
        choice = self.promotion_choice
        self.promotion_choice = None
        return choice

    def select(self, row, col):
        self.selected = (row, col)

    def record_capture(self, piece, row, col):
        """Remember a captured piece for snapshot rendering."""
        self.captured_pieces.append((piece, row, col))

    def add_score(self, color, points):
        self.score_by_color[color] = self.score_by_color.get(color, 0) + points

    def record_completed_move(
        self, piece_id, token, from_pos, requested_to, actual_to, reason
    ):
        self.completed_moves.append(
            {
                "piece_id": piece_id,
                "token": token,
                "from": from_pos,
                "requested_to": requested_to,
                "actual_to": actual_to,
                "reason": reason,
            }
        )
