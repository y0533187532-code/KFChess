"""Immutable reservation of a future airborne landing cell."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LandingReservation:
    piece_id: int
    color: str
    destination: tuple[int, int]

