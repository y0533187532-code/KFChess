"""Capture bookkeeping and score calculation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

try:
    from ..config import PIECE_SCORE_VALUES
    from .ports import ArbiterPort, ScorePolicy
except ImportError:
    from config import PIECE_SCORE_VALUES
    from engine.ports import ArbiterPort, ScorePolicy


@dataclass(frozen=True)
class MaterialScorePolicy:
    """Standard material-value scoring strategy."""

    points_by_piece_type: Mapping[str, int]

    def __init__(self, points_by_piece_type: Mapping[str, int] | None = None):
        values = PIECE_SCORE_VALUES if points_by_piece_type is None else points_by_piece_type
        object.__setattr__(
            self, "points_by_piece_type", MappingProxyType(dict(values))
        )

    def points_for(self, captured_piece) -> int:
        return self.points_by_piece_type.get(captured_piece.piece_type, 0)


class CaptureService:
    """Applies capture side effects without knowing movement mechanics."""

    def __init__(self, state, arbiter: ArbiterPort, score_policy: ScorePolicy):
        self._state = state
        self._arbiter = arbiter
        self._score_policy = score_policy

    def record(self, captured_piece, position, capturing_color: str) -> int:
        row, col = position
        self._state.record_capture(captured_piece, row, col)
        points_awarded = 0
        if captured_piece.color != capturing_color:
            points_awarded = self._score_policy.points_for(captured_piece)
            self._state.add_score(capturing_color, points_awarded)
        self._arbiter.clear_rest(captured_piece.piece_id)
        return points_awarded
