"""Screen identifiers and mutable presentation state for the OpenCV client."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ClientScreen(str, Enum):
    LOGIN = "login"
    REGISTER = "register"
    MAIN_MENU = "main_menu"
    PLAY_QUEUE = "play_queue"
    MATCH_FOUND = "match_found"
    ROOM_ENTRY = "room_entry"
    ROOM_LOBBY = "room_lobby"
    GAME_BOARD = "game_board"


class UiAction(str, Enum):
    SHOW_LOGIN = "show_login"
    SHOW_REGISTER = "show_register"
    SUBMIT_LOGIN = "submit_login"
    SUBMIT_REGISTER = "submit_register"
    PLAY = "play"
    PLAY_CANCEL = "play_cancel"
    ROOM = "room"
    ROOM_CREATE = "room_create"
    ROOM_JOIN = "room_join"
    ROOM_CANCEL = "room_cancel"
    ROOM_REFRESH = "room_refresh"
    ROOM_LEAVE = "room_leave"
    LOGOUT = "logout"


@dataclass(frozen=True)
class ClientUiConstraints:
    username_min_length: int
    username_max_length: int
    password_min_length: int
    room_code_length: int = 6

    @classmethod
    def from_config(cls, config):
        return cls(
            config.security.username_min_length,
            config.security.username_max_length,
            config.security.password_min_length,
        )


@dataclass
class ClientUiState:
    screen: ClientScreen = ClientScreen.LOGIN
    fields: dict[str, str] = field(
        default_factory=lambda: {
            "username": "",
            "password": "",
            "email": "",
            "phone": "",
            "room_code": "",
        }
    )
    active_field: str | None = None
    inline_message: str | None = None
    loading: bool = False
    queue_enqueued_at_ms: int | None = None
    queue_expires_at_ms: int | None = None
    now_ms: int = 0
    game_snapshot: object | None = None
    game_sequence: int | None = None
    game_lifecycle_state: str | None = None
    game_reconnect_deadline_ms: int | None = None
    game_selected_cell: tuple[int, int] | None = None
    game_selected_piece_id: int | None = None

    def display_value(self, field_name: str) -> str:
        value = self.fields[field_name]
        return "*" * len(value) if field_name == "password" else value

    @property
    def queue_seconds_remaining(self) -> int | None:
        if self.queue_expires_at_ms is None:
            return None
        remaining = max(0, self.queue_expires_at_ms - self.now_ms)
        return (remaining + 999) // 1000

    @property
    def queue_seconds_elapsed(self) -> int | None:
        if self.queue_enqueued_at_ms is None:
            return None
        return max(0, self.now_ms - self.queue_enqueued_at_ms) // 1000

    @property
    def reconnect_seconds_remaining(self) -> int | None:
        if self.game_reconnect_deadline_ms is None:
            return None
        remaining = max(0, self.game_reconnect_deadline_ms - self.now_ms)
        return (remaining + 999) // 1000
