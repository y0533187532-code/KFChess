"""Immutable snapshot of a piece removed from active play."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapturedPiece:
    """The stable identity and capture location of a removed piece."""

    piece_id: int | None
    token: str
    row: int
    col: int

    @property
    def position(self) -> tuple[int, int]:
        return self.row, self.col
