"""Authoritative gameplay sessions, commands, and tick scheduling."""

from .game_runtime_factory import GameRuntimeFactory, standard_starting_board
from .game_session import (
    CommandResult,
    GameSession,
    HandlerResult,
    SessionClosedError,
    SessionCommand,
    SessionCommandType,
)
from .gameplay_handlers import GameplayHandlers
from .gameplay_service import (
    BoardCoordinate,
    GameSnapshotRequest,
    GameplayCommandService,
    GameplayError,
    GameplayRequest,
    GameSessionRegistry,
    NetworkGameAdapter,
    build_game_session,
)
from .tick_scheduler import TickScheduler, needs_advancement

__all__ = [
    "BoardCoordinate",
    "CommandResult",
    "GameRuntimeFactory",
    "GameSession",
    "GameSessionRegistry",
    "GameSnapshotRequest",
    "GameplayCommandService",
    "GameplayError",
    "GameplayHandlers",
    "GameplayRequest",
    "HandlerResult",
    "NetworkGameAdapter",
    "SessionClosedError",
    "SessionCommand",
    "SessionCommandType",
    "TickScheduler",
    "build_game_session",
    "needs_advancement",
    "standard_starting_board",
]
