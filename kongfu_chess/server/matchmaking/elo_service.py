"""Pure Elo calculation for ranked Play results."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from ..core.chess_compatibility import CHESS_SEAT_ADAPTER, ChessOutcome
from ..core.game_mode import MatchOutcome


EloOutcome = MatchOutcome


@dataclass(frozen=True)
class EloResult:
    first_player_rating_before: int
    first_player_rating_after: int
    second_player_rating_before: int
    second_player_rating_after: int


class EloService:
    def __init__(self, *, scale: int, k_factor: int, rating_floor: int):
        self._scale = scale
        self._k_factor = k_factor
        self._rating_floor = rating_floor

    @classmethod
    def from_config(cls, config):
        return cls(
            scale=config.elo.scale,
            k_factor=config.elo.k_factor,
            rating_floor=config.elo.rating_floor,
        )

    def calculate(
        self,
        first_player_rating: int,
        second_player_rating: int,
        outcome: str | MatchOutcome | ChessOutcome,
    ) -> EloResult:
        try:
            resolved_outcome = MatchOutcome(outcome)
        except (TypeError, ValueError):
            resolved_outcome = CHESS_SEAT_ADAPTER.match_outcome(outcome)
        first_score, second_score = {
            MatchOutcome.FIRST_PLAYER_WIN: (Decimal("1"), Decimal("0")),
            MatchOutcome.SECOND_PLAYER_WIN: (Decimal("0"), Decimal("1")),
            MatchOutcome.DRAW: (Decimal("0.5"), Decimal("0.5")),
        }[resolved_outcome]
        first_expected = self._expected(first_player_rating, second_player_rating)
        second_expected = Decimal("1") - first_expected
        return EloResult(
            first_player_rating_before=first_player_rating,
            first_player_rating_after=self._updated(
                first_player_rating, first_score, first_expected
            ),
            second_player_rating_before=second_player_rating,
            second_player_rating_after=self._updated(
                second_player_rating, second_score, second_expected
            ),
        )

    @staticmethod
    def round_half_up(value: Decimal | str | float) -> int:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
        return int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def _expected(self, rating: int, opponent_rating: int) -> Decimal:
        exponent = (opponent_rating - rating) / self._scale
        expected = 1.0 / (1.0 + (10.0**exponent))
        return Decimal(str(expected))

    def _updated(self, rating: int, score: Decimal, expected: Decimal) -> int:
        raw = Decimal(rating) + Decimal(self._k_factor) * (score - expected)
        return max(self._rating_floor, self.round_half_up(raw))
