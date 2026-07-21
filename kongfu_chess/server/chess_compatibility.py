"""Translate neutral server seats to the current chess color contract."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType

from .game_mode import GameRole, MatchOutcome, PlayerSeat


class ChessColor(str, Enum):
    WHITE = "w"
    BLACK = "b"


class ChessOutcome(str, Enum):
    WHITE_WIN = "white_win"
    BLACK_WIN = "black_win"
    DRAW = "draw"


class ChessSeatAdapter:
    """The single White/Black compatibility boundary for server code."""

    _COLORS_BY_SEAT = MappingProxyType(
        {
            PlayerSeat.FIRST_PLAYER: ChessColor.WHITE,
            PlayerSeat.SECOND_PLAYER: ChessColor.BLACK,
        }
    )
    _OUTCOMES = MappingProxyType(
        {
            ChessOutcome.WHITE_WIN: MatchOutcome.FIRST_PLAYER_WIN,
            ChessOutcome.BLACK_WIN: MatchOutcome.SECOND_PLAYER_WIN,
            ChessOutcome.DRAW: MatchOutcome.DRAW,
        }
    )

    def color_for_player(self, seat: PlayerSeat) -> ChessColor:
        try:
            return self._COLORS_BY_SEAT[seat]
        except KeyError as exc:
            raise ValueError("This seat has no chess color mapping") from exc

    def protocol_color(self, seat: PlayerSeat) -> str:
        return self.color_for_player(seat).value

    def seat_for_color(self, color: str) -> PlayerSeat:
        try:
            chess_color = ChessColor(color)
            return next(
                seat
                for seat, mapped_color in self._COLORS_BY_SEAT.items()
                if mapped_color is chess_color
            )
        except (StopIteration, ValueError) as exc:
            raise ValueError("This chess color has no player-seat mapping") from exc

    def persistence_color(
        self, role: GameRole, seat: PlayerSeat | None
    ) -> str | None:
        if role is GameRole.SPECTATOR:
            return None
        if seat is None:
            raise ValueError("A chess player requires an assigned seat")
        return self.protocol_color(seat)

    def match_outcome(self, outcome: str | ChessOutcome) -> MatchOutcome:
        try:
            return self._OUTCOMES[ChessOutcome(outcome)]
        except (KeyError, ValueError) as exc:
            raise ValueError("Unsupported chess outcome") from exc


CHESS_SEAT_ADAPTER = ChessSeatAdapter()
