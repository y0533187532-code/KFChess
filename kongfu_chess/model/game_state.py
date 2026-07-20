"""Encapsulated mutable state owned by the engine layer."""

from __future__ import annotations

from types import MappingProxyType

try:
    from ..config import DEFAULT_VALID_COLORS
    from .captured_piece import CapturedPiece
    from .move_history import MoveHistory
except ImportError:
    from config import DEFAULT_VALID_COLORS
    from model.captured_piece import CapturedPiece
    from model.move_history import MoveHistory


class GameState:
    """Owns game progress and exposes mutations as named domain behaviors."""

    def __init__(self, board, move_history=None, player_colors=None):
        self._board = board
        self._game_over = False
        self._selected: tuple[int, int] | None = None
        self._promotion_choice: str | None = None
        self._captured_pieces: list[CapturedPiece] = []
        configured_colors = (
            getattr(board, "valid_colors", DEFAULT_VALID_COLORS)
            if player_colors is None
            else frozenset(player_colors)
        )
        self._score_by_color = {
            color: 0 for color in configured_colors
        }
        self._move_history = move_history or MoveHistory()

    @property
    def board(self):
        return self._board

    @property
    def is_game_over(self) -> bool:
        return self._game_over

    @property
    def selected(self) -> tuple[int, int] | None:
        return self._selected

    @property
    def promotion_choice(self) -> str | None:
        return self._promotion_choice

    @property
    def captured_pieces(self) -> tuple[CapturedPiece, ...]:
        return tuple(self._captured_pieces)

    @property
    def score_by_color(self):
        return MappingProxyType(self._score_by_color)

    @property
    def completed_moves(self) -> tuple:
        return self._move_history.legacy_events

    @property
    def move_history(self):
        return self._move_history

    def mark_game_over(self) -> None:
        self._game_over = True

    def set_game_over(self, value: bool) -> None:
        """Compatibility behavior for callers restoring a saved game state."""
        self._game_over = bool(value)

    def clear_selection(self) -> None:
        self._selected = None

    def set_promotion_choice(self, piece_type: str) -> None:
        self._promotion_choice = piece_type

    def consume_promotion_choice(self) -> str | None:
        choice = self._promotion_choice
        self._promotion_choice = None
        return choice

    def select(self, row: int, col: int) -> None:
        self._selected = (row, col)

    def record_capture(self, piece, row: int, col: int) -> None:
        self._captured_pieces.append(
            CapturedPiece(
                piece_id=piece.piece_id,
                token=piece.token,
                row=row,
                col=col,
            )
        )

    def add_score(self, color: str, points: int) -> None:
        self._score_by_color[color] = self._score_by_color.get(color, 0) + points
