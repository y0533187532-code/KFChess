"""Configurable policy for how a moving piece occupies the board."""

from __future__ import annotations

from enum import Enum

try:
    from ..config import KNIGHT_PIECE_TYPE
except ImportError:
    from config import KNIGHT_PIECE_TYPE


class MovementMode(str, Enum):
    """Logical occupancy behavior used while a piece is travelling."""

    GROUNDED = "grounded"
    AIRBORNE = "airborne"


DEFAULT_AIRBORNE_PIECE_TYPES = frozenset({KNIGHT_PIECE_TYPE})


class MovementPolicy:
    """Select a movement mode without coupling the engine to piece codes."""

    def __init__(self, airborne_piece_types=None):
        values = (
            DEFAULT_AIRBORNE_PIECE_TYPES
            if airborne_piece_types is None
            else airborne_piece_types
        )
        self._airborne_piece_types = frozenset(values)

    @property
    def airborne_piece_types(self):
        return self._airborne_piece_types

    def mode_for(self, piece) -> MovementMode:
        if piece.piece_type in self._airborne_piece_types:
            return MovementMode.AIRBORNE
        return MovementMode.GROUNDED

