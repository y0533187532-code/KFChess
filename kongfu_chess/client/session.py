"""Client-owned authentication, room, and matched-game session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ClientGameSession:
    game_id: str
    game_token: str = field(repr=False)
    role: str
    seat: str | None
    color: str | None
    mode: str
    ranked: bool


@dataclass(frozen=True)
class ClientRoomSession:
    room_id: int
    code: str
    game_id: str
    status: str
    role: str
    seat: str | None
    color: str | None
    player_count: int
    spectator_count: int
    gameplay_started: bool


class ClientSessionState:
    """Keep raw tokens internal and redact them from representations."""

    def __init__(self):
        self.user_id: int | None = None
        self.username: str | None = None
        self.rating: int | None = None
        self.expires_at_ms: int | None = None
        self._auth_token: str | None = None
        self.game: ClientGameSession | None = None
        self.room: ClientRoomSession | None = None

    @property
    def authenticated(self) -> bool:
        return self._auth_token is not None

    def require_auth_token(self) -> str:
        if self._auth_token is None:
            raise RuntimeError("Authentication is required")
        return self._auth_token

    def authenticate(self, payload: Mapping) -> None:
        self.user_id = int(payload["user_id"])
        self.username = str(payload["username"])
        self.rating = int(payload["rating"])
        self.expires_at_ms = int(payload["expires_at_ms"])
        self._auth_token = str(payload["auth_token"])

    def refresh_principal(self, payload: Mapping) -> None:
        if not self.authenticated:
            raise RuntimeError("Authentication is required")
        self.user_id = int(payload["user_id"])
        self.username = str(payload["username"])
        self.rating = int(payload["rating"])

    def store_play_match(self, payload: Mapping) -> None:
        self.game = ClientGameSession(
            game_id=str(payload["game_id"]),
            game_token=str(payload["game_token"]),
            role=str(payload["role"]),
            seat=str(payload["seat"]),
            color=str(payload["color"]),
            mode=str(payload.get("mode", "PLAY")),
            ranked=bool(payload.get("ranked", True)),
        )
        self.room = None

    def store_room(self, payload: Mapping) -> None:
        seat = payload.get("seat")
        color = payload.get("color")
        self.room = ClientRoomSession(
            room_id=int(payload["room_id"]),
            code=str(payload["code"]),
            game_id=str(payload["game_id"]),
            status=str(payload["status"]),
            role=str(payload["role"]),
            seat=None if seat is None else str(seat),
            color=None if color is None else str(color),
            player_count=int(payload["player_count"]),
            spectator_count=int(payload["spectator_count"]),
            gameplay_started=bool(payload["gameplay_started"]),
        )
        token = payload.get("game_token")
        if token is not None:
            self.game = ClientGameSession(
                game_id=self.room.game_id,
                game_token=str(token),
                role=self.room.role,
                seat=self.room.seat,
                color=self.room.color,
                mode="ROOM",
                ranked=False,
            )

    def clear_room(self) -> None:
        if self.game is not None and self.game.mode == "ROOM":
            self.game = None
        self.room = None

    def clear(self) -> None:
        self.user_id = None
        self.username = None
        self.rating = None
        self.expires_at_ms = None
        self._auth_token = None
        self.game = None
        self.room = None

    def __repr__(self) -> str:
        return (
            "ClientSessionState("
            f"user_id={self.user_id!r}, username={self.username!r}, "
            f"rating={self.rating!r}, authenticated={self.authenticated!r}, "
            f"game={self.game!r}, room={self.room!r})"
        )
