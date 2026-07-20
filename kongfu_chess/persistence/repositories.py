"""Compatibility exports for repositories split by responsibility."""

from .auth_session_repository import AuthSessionRepository
from .game_token_repository import GameTokenRepository
from .match_repository import MatchRepository
from .room_repository import RoomRepository
from .user_repository import UserRepository

__all__ = [
    "AuthSessionRepository",
    "GameTokenRepository",
    "MatchRepository",
    "RoomRepository",
    "UserRepository",
]
