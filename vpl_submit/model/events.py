"""Immutable domain events published after game state transitions complete."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MoveCompletedEvent:
    piece_id: int
    token: str
    from_pos: tuple[int, int]
    requested_to: tuple[int, int]
    actual_to: tuple[int, int]
    reason: str


@dataclass(frozen=True)
class PieceCapturedEvent:
    captured_piece_id: int
    captured_token: str
    capturing_color: str
    position: tuple[int, int]
    points_awarded: int


@dataclass(frozen=True)
class GameOverEvent:
    winning_color: str
    captured_piece_id: int
