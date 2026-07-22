"""Neutral server-layer game modes, participant roles, and player seats."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol, Sequence


class PlayerSeat(str, Enum):
    FIRST_PLAYER = "FIRST_PLAYER"
    SECOND_PLAYER = "SECOND_PLAYER"


class GameRole(str, Enum):
    PLAYER = "PLAYER"
    SPECTATOR = "SPECTATOR"


class GameMode(str, Enum):
    PLAY = "PLAY"
    ROOM = "ROOM"


class MatchOutcome(str, Enum):
    FIRST_PLAYER_WIN = "first_player_win"
    SECOND_PLAYER_WIN = "second_player_win"
    DRAW = "draw"


@dataclass(frozen=True)
class GameModeConfig:
    mode: GameMode
    player_seats: tuple[PlayerSeat, ...]
    ranked: bool

    def __post_init__(self) -> None:
        if not self.player_seats:
            raise ValueError("A game mode must define at least one player seat")
        if len(set(self.player_seats)) != len(self.player_seats):
            raise ValueError("Game-mode player seats must be unique")


PLAY_GAME_MODE = GameModeConfig(
    mode=GameMode.PLAY,
    player_seats=(PlayerSeat.FIRST_PLAYER, PlayerSeat.SECOND_PLAYER),
    ranked=True,
)

ROOM_GAME_MODE = GameModeConfig(
    mode=GameMode.ROOM,
    player_seats=(PlayerSeat.FIRST_PLAYER, PlayerSeat.SECOND_PLAYER),
    ranked=False,
)


@dataclass(frozen=True)
class SeatAssignment:
    user_id: int
    seat: PlayerSeat


class SeatBoundaryAdapter(Protocol):
    def persistence_color(
        self, role: GameRole, seat: PlayerSeat | None
    ) -> str | None: ...

    def protocol_color(self, seat: PlayerSeat) -> str: ...

    def seat_for_color(self, color: str) -> PlayerSeat: ...


class SeatAssignmentPolicy:
    """Assign players to the neutral seats declared by a game mode."""

    def __init__(
        self,
        order_selector: Callable[[tuple[int, ...]], Sequence[int]] | None = None,
    ):
        self._order_selector = order_selector or self._random_order

    def assign(
        self, user_ids: Sequence[int], game_mode: GameModeConfig
    ) -> tuple[SeatAssignment, ...]:
        players = tuple(user_ids)
        if len(players) != len(game_mode.player_seats):
            raise ValueError("Player count must match the configured player seats")
        ordered_players = tuple(self._order_selector(players))
        if (
            len(ordered_players) != len(players)
            or len(set(ordered_players)) != len(players)
            or set(ordered_players) != set(players)
        ):
            raise ValueError("Seat selector must return every player exactly once")
        return tuple(
            SeatAssignment(user_id, seat)
            for seat, user_id in zip(game_mode.player_seats, ordered_players)
        )

    @staticmethod
    def _random_order(user_ids: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(secrets.SystemRandom().sample(user_ids, k=len(user_ids)))
