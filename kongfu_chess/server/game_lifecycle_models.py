"""Shared application-layer values for authoritative game lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..protocol import ProtocolErrorCode
from .game_mode import GameMode, PlayerSeat


class GameLifecycleState(str, Enum):
    CREATED = "CREATED"
    WAITING_TO_START = "WAITING_TO_START"
    ACTIVE = "ACTIVE"
    PAUSED_FOR_RECONNECT = "PAUSED_FOR_RECONNECT"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


TERMINAL_LIFECYCLE_STATES = frozenset(
    {
        GameLifecycleState.ENDED,
        GameLifecycleState.CANCELLED,
        GameLifecycleState.INTERRUPTED,
    }
)

LIVE_LIFECYCLE_STATE_VALUES = frozenset(
    {
        GameLifecycleState.CREATED.value,
        GameLifecycleState.WAITING_TO_START.value,
        GameLifecycleState.ACTIVE.value,
        GameLifecycleState.PAUSED_FOR_RECONNECT.value,
    }
)


class GameLifecycleError(ValueError):
    def __init__(self, code: ProtocolErrorCode):
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class LifecyclePlayer:
    user_id: int
    seat: PlayerSeat
    connected: bool
    reconnect_deadline_ms: int | None
    meaningful_activity: bool


@dataclass(frozen=True)
class GameLifecycleView:
    game_id: str
    mode: GameMode
    ranked: bool
    state: GameLifecycleState
    players: tuple[LifecyclePlayer, ...]
    version: int
    reconnect_deadline_ms: int | None
    winner_seat: PlayerSeat | None
    terminal_reason: str | None
    changed: bool = True
