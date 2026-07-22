"""Immutable, injectable text and sizing settings for the game view."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from kongfu_chess.config import (
    BISHOP_PIECE_TYPE,
    BLACK_COLOR,
    KING_PIECE_TYPE,
    KNIGHT_PIECE_TYPE,
    PAWN_PIECE_TYPE,
    QUEEN_PIECE_TYPE,
    ROOK_PIECE_TYPE,
    WHITE_COLOR,
)


DEFAULT_PLAYER_NAMES = {
    WHITE_COLOR: "White Player",
    BLACK_COLOR: "Black Player",
}

DEFAULT_PIECE_TYPE_NAMES = {
    KING_PIECE_TYPE: "King",
    QUEEN_PIECE_TYPE: "Queen",
    ROOK_PIECE_TYPE: "Rook",
    BISHOP_PIECE_TYPE: "Bishop",
    KNIGHT_PIECE_TYPE: "Knight",
    PAWN_PIECE_TYPE: "Pawn",
}

DEFAULT_MAX_MOVE_LOG_LINES = 8


@dataclass(frozen=True)
class ViewSettings:
    """Configuration shared by renderer-facing layout collaborators."""

    player_names: Mapping[str, str]
    piece_type_names: Mapping[str, str]
    max_move_log_lines: int
    time_column_header: str
    move_column_header: str
    score_label: str
    moves_label: str
    rtl: bool

    def __init__(
        self,
        player_names: Mapping[str, str] | None = None,
        piece_type_names: Mapping[str, str] | None = None,
        max_move_log_lines: int = DEFAULT_MAX_MOVE_LOG_LINES,
        time_column_header: str = "Time",
        move_column_header: str = "Move",
        score_label: str = "Score",
        moves_label: str = "Moves",
        rtl: bool = False,
    ):
        resolved_players = (
            DEFAULT_PLAYER_NAMES if player_names is None else player_names
        )
        resolved_piece_names = (
            DEFAULT_PIECE_TYPE_NAMES
            if piece_type_names is None
            else piece_type_names
        )
        if len(resolved_players) != 2:
            raise ValueError("The current side-panel layout requires two players")
        if max_move_log_lines <= 0:
            raise ValueError("max_move_log_lines must be positive")

        object.__setattr__(
            self,
            "player_names",
            MappingProxyType(dict(resolved_players)),
        )
        object.__setattr__(
            self,
            "piece_type_names",
            MappingProxyType(dict(resolved_piece_names)),
        )
        object.__setattr__(self, "max_move_log_lines", max_move_log_lines)
        object.__setattr__(self, "time_column_header", time_column_header)
        object.__setattr__(self, "move_column_header", move_column_header)
        object.__setattr__(self, "score_label", score_label)
        object.__setattr__(self, "moves_label", moves_label)
        object.__setattr__(self, "rtl", rtl)

    @property
    def player_colors(self) -> tuple[str, str]:
        colors = tuple(self.player_names)
        return colors[0], colors[1]
