"""Board cell coordinates (value object)."""

from dataclasses import dataclass


@dataclass(frozen=True, eq=True)
class Position:
    row: int
    col: int

    def __repr__(self):
        return f"Position({self.row}, {self.col})"
