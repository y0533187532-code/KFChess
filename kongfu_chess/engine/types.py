"""Public API result types for engine and rules layers (Phase 0 skeleton)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MoveValidation:
    is_valid: bool
    reason: str


@dataclass(frozen=True)
class MoveResult:
    is_accepted: bool
    reason: str


@dataclass(frozen=True)
class GameSnapshot:
    board_width: int
    board_height: int
    game_over: bool
    selected: tuple | None = None
    pieces: tuple = field(default_factory=tuple)
