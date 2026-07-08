"""A single chess piece.

A Piece only knows its own color and type code. It has no idea how (or
whether) a Board stores it internally - that is the Board's business, not
its own (encapsulation).

Validity is checked against a rule-set that is *passed in*, never against
a hard-coded list. This is what lets a future "design your own game"
feature define entirely different piece types/colors and still reuse this
class unmodified.
"""

from dataclasses import dataclass

from .config import TOKEN_LENGTH


@dataclass(frozen=True)
class Piece:
    color: str
    piece_type: str

    def is_valid(self, valid_colors, valid_piece_types):
        """Check this piece against a caller-supplied rule-set."""
        return self.color in valid_colors and self.piece_type in valid_piece_types

    @property
    def token(self):
        """Canonical 2-character token for this piece, e.g. 'wP'.

        This is reconstructed from the piece's validated state, not stored
        from the original input string - so re-serializing a Board always
        yields a normalized ("canonical") token, regardless of how the raw
        input was spaced or formatted.
        """
        return f"{self.color}{self.piece_type}"

    @classmethod
    def from_token(cls, token):
        """Build a Piece from a token such as ``"wP"``.

        Returns None if the token isn't shaped like a piece token at all
        (wrong length). This is a purely structural check; whether the
        resulting color/type are *actually* valid is decided by
        ``is_valid`` against the active rule-set, not by this method.
        """
        if len(token) != TOKEN_LENGTH:
            return None
        color, piece_type = token[0], token[1]
        return cls(color=color, piece_type=piece_type)
