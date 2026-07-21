"""Authoritative server application components."""

from .game_session import (
    CommandResult,
    GameSession,
    HandlerResult,
    SessionClosedError,
    SessionCommand,
    SessionCommandType,
)
from .connections import ConnectionRegistry
from .auth_service import (
    AuthError,
    AuthPrincipal,
    AuthService,
    AuthenticatedSession,
    RegisteredAccount,
    build_auth_service,
)
from .password_hasher import PasswordHasher
from .auth_handlers import AuthHandlers
from .elo_service import EloOutcome, EloResult, EloService
from .chess_compatibility import (
    CHESS_SEAT_ADAPTER,
    ChessColor,
    ChessOutcome,
    ChessSeatAdapter,
)
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
from .gameplay_handlers import GameplayHandlers
from .gameplay_service import (
    BoardCoordinate,
    GameplayCommandService,
    GameplayError,
    GameplayRequest,
    GameSessionRegistry,
    NetworkGameAdapter,
    build_game_session,
)
from .matchmaking_service import (
    MatchmakingError,
    MatchmakingService,
    MatchmakingStatus,
    PlayMatch,
    PlayMatchView,
    PlaySeat,
    QueueTicket,
)
from .matchmaking_handlers import MatchmakingHandlers
from .rooms_handlers import RoomsHandlers
from .room_models import RoomStatus, RoomsError, RoomView
from .rooms_service import RoomsService
from .room_code_policy import RoomCodePolicy
from .room_seating_policy import RoomAssignment, RoomSeatingPolicy
from .room_view_factory import RoomViewFactory
from .routing import MessageRouter, OutgoingMessage, RequestContext
from .websocket_gateway import WebSocketGateway

__all__ = [
    "CommandResult",
    "BoardCoordinate",
    "ConnectionRegistry",
    "CHESS_SEAT_ADAPTER",
    "ChessColor",
    "ChessOutcome",
    "ChessSeatAdapter",
    "EloOutcome",
    "EloResult",
    "EloService",
    "MatchmakingError",
    "MatchmakingHandlers",
    "MatchmakingService",
    "MatchmakingStatus",
    "MatchOutcome",
    "AuthError",
    "AuthHandlers",
    "AuthPrincipal",
    "AuthService",
    "AuthenticatedSession",
    "GameSession",
    "GameMode",
    "GameModeConfig",
    "GameRole",
    "GameplayCommandService",
    "GameplayError",
    "GameplayHandlers",
    "GameplayRequest",
    "GameSessionRegistry",
    "HandlerResult",
    "MessageRouter",
    "NetworkGameAdapter",
    "OutgoingMessage",
    "PasswordHasher",
    "PLAY_GAME_MODE",
    "PlayerSeat",
    "PlayMatch",
    "PlayMatchView",
    "PlaySeat",
    "QueueTicket",
    "RequestContext",
    "RoomAssignment",
    "RoomCodePolicy",
    "RoomSeatingPolicy",
    "RoomStatus",
    "RoomsError",
    "RoomsHandlers",
    "RoomsService",
    "RoomView",
    "RoomViewFactory",
    "ROOM_GAME_MODE",
    "RegisteredAccount",
    "build_auth_service",
    "build_game_session",
    "SessionClosedError",
    "SessionCommand",
    "SessionCommandType",
    "SeatAssignment",
    "SeatAssignmentPolicy",
    "SeatBoundaryAdapter",
    "WebSocketGateway",
]
