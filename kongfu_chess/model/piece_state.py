"""Lifecycle states exposed by immutable game snapshots."""

from __future__ import annotations

from enum import Enum


class PieceState(str, Enum):
    """Renderer-facing state derived from board and arbiter data."""

    IDLE = "idle"
    MOVING = "moving"
    JUMPING = "jump"
    RESTING = "resting"
    CAPTURED = "captured"

    def __str__(self) -> str:
        return self.value


# Backwards-compatible public names. New code should use PieceState directly.
PIECE_STATE_IDLE = PieceState.IDLE
PIECE_STATE_MOVING = PieceState.MOVING
PIECE_STATE_JUMPING = PieceState.JUMPING
PIECE_STATE_RESTING = PieceState.RESTING
PIECE_STATE_CAPTURED = PieceState.CAPTURED
