"""Public API result types for engine and rules layers (Phase 0 skeleton)."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

try:
    from ..model.piece import PIECE_STATE_IDLE
except ImportError:
    from model.piece import PIECE_STATE_IDLE


@dataclass(frozen=True)
class MoveValidation:
    is_valid: bool
    reason: str


@dataclass(frozen=True)
class MoveResult:
    is_accepted: bool
    reason: str


@dataclass(frozen=True)
class PieceSnapshot:
    """Read-only piece view for rendering (row, col, token, piece_id, state)."""

    row: int
    col: int
    token: str
    piece_id: int
    state: str = PIECE_STATE_IDLE
    rest_remaining_ms: int | None = None


@dataclass(frozen=True)
class MoveEventSnapshot:
    piece_id: int
    token: str
    from_pos: tuple[int, int]
    requested_to: tuple[int, int]
    actual_to: tuple[int, int]
    reason: str


@dataclass(frozen=True)
class GameSnapshot:
    """Read-only view model / DTO for the renderer and diagnostics."""

    board_width: int
    board_height: int
    game_over: bool
    selected: tuple[int, int] | None = None
    pieces: tuple[PieceSnapshot, ...] = field(default_factory=tuple)
    legal_destinations: tuple[tuple[int, int], ...] = field(default_factory=tuple)
    score_by_color: Mapping[str, int] = field(default_factory=dict)
    completed_moves: tuple[MoveEventSnapshot, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "score_by_color", MappingProxyType(dict(self.score_by_color))
        )
