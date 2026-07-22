"""Shared server core types, chess adapters, and logging."""

from .chess_compatibility import (
    CHESS_SEAT_ADAPTER,
    ChessColor,
    ChessOutcome,
    ChessSeatAdapter,
)
from .event_logger import ServerEventLogger
from .game_mode import (
    PLAY_GAME_MODE,
    ROOM_GAME_MODE,
    GameMode,
    GameModeConfig,
    GameRole,
    MatchOutcome,
    PlayerSeat,
    SeatAssignment,
    SeatAssignmentPolicy,
    SeatBoundaryAdapter,
)

__all__ = [
    "CHESS_SEAT_ADAPTER",
    "ChessColor",
    "ChessOutcome",
    "ChessSeatAdapter",
    "GameMode",
    "GameModeConfig",
    "GameRole",
    "MatchOutcome",
    "PLAY_GAME_MODE",
    "PlayerSeat",
    "ROOM_GAME_MODE",
    "SeatAssignment",
    "SeatAssignmentPolicy",
    "SeatBoundaryAdapter",
    "ServerEventLogger",
]
