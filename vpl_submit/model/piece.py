"""The stable identity and intrinsic attributes of a chess piece.

A Piece only knows its own identifier, color, and type code. It has no idea how (or
whether) a Board stores it internally - that is the Board's business, not
its own (encapsulation).

Validity is checked against a rule-set that is *passed in*, never against
a hard-coded list. This is what lets a future "design your own game"
feature define entirely different piece types/colors and still reuse this
class unmodified.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from ..config import TOKEN_LENGTH
except ImportError:
    from config import TOKEN_LENGTH

# Compatibility re-exports for callers that imported lifecycle constants from
# this module before state ownership moved to ``piece_state``.
try:
    from .piece_state import (
        PIECE_STATE_CAPTURED,
        PIECE_STATE_IDLE,
        PIECE_STATE_JUMPING,
        PIECE_STATE_MOVING,
        PIECE_STATE_RESTING,
    )
except ImportError:
    from piece_state import (
        PIECE_STATE_CAPTURED,
        PIECE_STATE_IDLE,
        PIECE_STATE_JUMPING,
        PIECE_STATE_MOVING,
        PIECE_STATE_RESTING,
    )


@dataclass(frozen=True)
class Piece:
    color: str
    piece_type: str
    piece_id: int | None = None

    def is_valid(self, valid_colors, valid_piece_types):
        """Check this piece against a caller-supplied rule-set."""
        return self.color in valid_colors and self.piece_type in valid_piece_types

    @property
    def token(self):
        """Canonical 2-character token for this piece, e.g. 'wP'."""
        return f"{self.color}{self.piece_type}"

    @classmethod
    def from_token(cls, token, piece_id=None):
        """Build a Piece from a token such as ``"wP"``."""
        if len(token) != TOKEN_LENGTH:
            return None
        color, piece_type = token[0], token[1]
        return cls(
            color=color,
            piece_type=piece_type,
            piece_id=piece_id,
        )

    def with_piece_type(self, piece_type):
        """Return a copy of this piece with an updated type (e.g. promotion)."""
        return Piece(
            color=self.color,
            piece_type=piece_type,
            piece_id=self.piece_id,
        )
