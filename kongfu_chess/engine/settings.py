"""Immutable runtime settings for the game engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

try:
    from ..config import (
        DEFAULT_JUMP_DURATION_MS,
        DEFAULT_MOVE_DURATION_MS,
        DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE,
        KING_PIECE_TYPE,
    )
except ImportError:
    from config import (
        DEFAULT_JUMP_DURATION_MS,
        DEFAULT_MOVE_DURATION_MS,
        DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE,
        KING_PIECE_TYPE,
    )


def _immutable_copy(values: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True)
class EngineSettings:
    """Validated values that control timing and the game-over condition."""

    move_durations_ms: Mapping[str, int] = field(
        default_factory=lambda: dict(DEFAULT_MOVE_DURATION_MS)
    )
    jump_duration_ms: int = DEFAULT_JUMP_DURATION_MS
    rest_durations_ms: Mapping[str, int] = field(
        default_factory=lambda: dict(DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE)
    )
    game_over_piece_type: str = KING_PIECE_TYPE

    def __post_init__(self) -> None:
        self._validate_durations(self.move_durations_ms, "move")
        self._validate_durations(self.rest_durations_ms, "rest")
        if self.jump_duration_ms < 0:
            raise ValueError("jump duration cannot be negative")
        object.__setattr__(
            self, "move_durations_ms", _immutable_copy(self.move_durations_ms)
        )
        object.__setattr__(
            self, "rest_durations_ms", _immutable_copy(self.rest_durations_ms)
        )

    @classmethod
    def from_overrides(
        cls,
        *,
        move_durations: Mapping[str, int] | None = None,
        jump_duration_ms: int | None = None,
        rest_durations: Mapping[str, int] | None = None,
        game_over_piece_type: str | None = None,
    ) -> "EngineSettings":
        move_values = dict(DEFAULT_MOVE_DURATION_MS)
        if move_durations is not None:
            move_values.update(move_durations)

        rest_values = dict(DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE)
        if rest_durations is not None:
            rest_values.update(rest_durations)

        return cls(
            move_durations_ms=move_values,
            jump_duration_ms=(
                DEFAULT_JUMP_DURATION_MS
                if jump_duration_ms is None
                else jump_duration_ms
            ),
            rest_durations_ms=rest_values,
            game_over_piece_type=(
                KING_PIECE_TYPE
                if game_over_piece_type is None
                else game_over_piece_type
            ),
        )

    def move_duration_for(self, piece_type: str) -> int:
        try:
            return self.move_durations_ms[piece_type]
        except KeyError as error:
            raise ValueError(
                f"No move duration is configured for piece type {piece_type!r}"
            ) from error

    def rest_duration_for(self, piece_type: str) -> int:
        return self.rest_durations_ms.get(piece_type, 0)

    @staticmethod
    def _validate_durations(values: Mapping[str, int], label: str) -> None:
        invalid = [piece_type for piece_type, value in values.items() if value < 0]
        if invalid:
            raise ValueError(
                f"{label} durations cannot be negative: {', '.join(sorted(invalid))}"
            )
