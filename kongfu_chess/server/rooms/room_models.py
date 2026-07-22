"""Room application-layer values shared by room policies and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from ...protocol import ProtocolErrorCode
from ..core.game_mode import GameRole, PlayerSeat


class RoomStatus(str, Enum):
    WAITING = "WAITING"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    INTERRUPTED = "INTERRUPTED"
    ENDED = "ENDED"


class RoomsError(ValueError):
    def __init__(self, code: ProtocolErrorCode):
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class RoomView:
    room_id: int
    code: str
    game_id: str
    status: RoomStatus
    role: GameRole
    seat: PlayerSeat | None
    game_token: str | None
    player_count: int
    spectator_count: int
    gameplay_started: bool
    snapshot: Mapping | None = None
    leave_deferred: bool = False
