"""Compatibility exports for repositories split by responsibility."""

from .auth_session_repository import AuthSessionRepository
from .game_token_repository import GameTokenRepository
from .game_lifecycle_repository import GameLifecycleRepository
from .match_repository import MatchRepository
from .room_repository import RoomRepository
from .user_repository import UserRepository

__all__ = [
    "AuthSessionRepository",
    "GameTokenRepository",
    "GameLifecycleRepository",
    "MatchRepository",
    "RoomRepository",
    "UserRepository",
]
