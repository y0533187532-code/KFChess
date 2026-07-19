"""Identity registry for pieces that belong to one game board."""

from __future__ import annotations

from dataclasses import replace as dataclass_replace

try:
    from ..errors import DuplicatePieceIdError, UnknownPieceIdError
    from .piece import Piece
except ImportError:
    from errors import DuplicatePieceIdError, UnknownPieceIdError
    from piece import Piece


class PieceRegistry:
    """Own stable piece identities independently of board occupancy."""

    def __init__(self) -> None:
        self._pieces_by_id: dict[int, Piece] = {}
        self._active_ids: set[int] = set()
        self._next_piece_id = 0

    def register(self, piece: Piece) -> Piece:
        """Register and activate a new identity, assigning an ID when absent."""
        if piece.piece_id is None:
            piece = dataclass_replace(piece, piece_id=self._allocate_id())
        elif piece.piece_id in self._pieces_by_id:
            raise DuplicatePieceIdError(piece.piece_id)
        else:
            self._advance_sequence_past(piece.piece_id)

        self._pieces_by_id[piece.piece_id] = piece
        self._active_ids.add(piece.piece_id)
        return piece

    def deactivate(self, piece: Piece) -> None:
        """Mark a known piece as temporarily or permanently absent from the board."""
        self._require_canonical_piece(piece)
        self._active_ids.discard(piece.piece_id)

    def reactivate(self, piece: Piece) -> None:
        """Reactivate the same canonical object after temporary removal."""
        self._require_canonical_piece(piece)
        if piece.piece_id in self._active_ids:
            raise DuplicatePieceIdError(piece.piece_id)
        self._active_ids.add(piece.piece_id)

    def replace_piece(self, current_piece: Piece, replacement_piece: Piece) -> None:
        """Replace intrinsic attributes while preserving one registered identity."""
        self._require_canonical_piece(current_piece)
        if replacement_piece.piece_id != current_piece.piece_id:
            raise DuplicatePieceIdError(replacement_piece.piece_id)
        self._pieces_by_id[current_piece.piece_id] = replacement_piece

    def _require_canonical_piece(self, piece: Piece) -> None:
        registered_piece = self._pieces_by_id.get(piece.piece_id)
        if registered_piece is None:
            raise UnknownPieceIdError(piece.piece_id)
        if registered_piece is not piece:
            raise DuplicatePieceIdError(piece.piece_id)

    def _allocate_id(self) -> int:
        while self._next_piece_id in self._pieces_by_id:
            self._next_piece_id += 1
        piece_id = self._next_piece_id
        self._next_piece_id += 1
        return piece_id

    def _advance_sequence_past(self, piece_id: int) -> None:
        if piece_id >= self._next_piece_id:
            self._next_piece_id = piece_id + 1
