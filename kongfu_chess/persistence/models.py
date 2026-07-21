"""Immutable records returned by persistence repositories."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    password_hash: str
    email: str | None
    phone: str | None
    rating: int
    status: str


@dataclass(frozen=True)
class AuthSessionRecord:
    id: int
    user_id: int
    expires_at_ms: int
    last_used_at_ms: int


@dataclass(frozen=True)
class AuthSessionValidation:
    status: str
    session: AuthSessionRecord | None


@dataclass(frozen=True)
class GameTokenRecord:
    id: int
    game_id: str
    user_id: int
    role: str
    color: str | None
    status: str
    grace_expires_at_ms: int | None


@dataclass(frozen=True)
class RoomRecord:
    id: int
    code: str
    game_id: str
    creator_user_id: int | None
    status: str
    started_at_ms: int | None


@dataclass(frozen=True)
class RoomMemberRecord:
    id: int
    room_id: int
    user_id: int | None
    role: str
    color: str | None
    joined_at_ms: int
    left_at_ms: int | None
