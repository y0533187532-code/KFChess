"""Neutral player-seat and spectator assignment for current MVP rooms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection

from ..core.game_mode import ROOM_GAME_MODE, GameModeConfig, GameRole, PlayerSeat


@dataclass(frozen=True)
class RoomAssignment:
    role: GameRole
    seat: PlayerSeat | None


class RoomSeatingPolicy:
    """Assign room participation without any chess or UI color concepts."""

    def __init__(self, game_mode: GameModeConfig = ROOM_GAME_MODE):
        if len(game_mode.player_seats) != 2:
            raise ValueError("Current MVP rooms require exactly two player seats")
        self._creator_seat, self._opponent_seat = game_mode.player_seats

    def assign_creator(self) -> RoomAssignment:
        return RoomAssignment(GameRole.PLAYER, self._creator_seat)

    def assign_joiner(
        self,
        occupied_seats: Collection[PlayerSeat],
        *,
        gameplay_started: bool,
    ) -> RoomAssignment:
        if not gameplay_started and self._opponent_seat not in occupied_seats:
            return RoomAssignment(GameRole.PLAYER, self._opponent_seat)
        return RoomAssignment(GameRole.SPECTATOR, None)

    @property
    def creator_seat(self) -> PlayerSeat:
        return self._creator_seat

    @property
    def opponent_seat(self) -> PlayerSeat:
        return self._opponent_seat
