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
class PieceSnapshot:
    """Read-only piece view for rendering (row, col, token, piece_id, state)."""

    row: int
    col: int
    token: str
    piece_id: int
    state: str = "idle"


@dataclass(frozen=True)
class GameSnapshot:
    """Read-only view model / DTO for the renderer and diagnostics."""

    board_width: int
    board_height: int
    game_over: bool
    selected: tuple | None = None
    pieces: tuple[PieceSnapshot, ...] = field(default_factory=tuple)
