import pytest

from kongfu_chess.errors import DuplicatePieceIdError, UnknownPieceIdError
from kongfu_chess.model.piece import Piece
from kongfu_chess.model.piece_registry import PieceRegistry


def test_register_assigns_stable_sequential_ids():
    registry = PieceRegistry()

    first = registry.register(Piece.from_token("wK"))
    second = registry.register(Piece.from_token("bK"))

    assert first.piece_id == 0
    assert second.piece_id == 1


def test_explicit_id_advances_automatic_id_sequence():
    registry = PieceRegistry()
    registry.register(Piece.from_token("wK", piece_id=10))

    automatic = registry.register(Piece.from_token("bK"))

    assert automatic.piece_id == 11


def test_deactivated_id_cannot_be_registered_to_another_object():
    registry = PieceRegistry()
    original = registry.register(Piece.from_token("wK"))
    registry.deactivate(original)

    with pytest.raises(DuplicatePieceIdError):
        registry.register(Piece.from_token("bK", piece_id=original.piece_id))


def test_only_canonical_object_can_be_reactivated():
    registry = PieceRegistry()
    original = registry.register(Piece.from_token("wK"))
    registry.deactivate(original)
    impostor = Piece.from_token("wK", piece_id=original.piece_id)

    with pytest.raises(DuplicatePieceIdError):
        registry.reactivate(impostor)

    registry.reactivate(original)


def test_unknown_piece_cannot_be_reactivated():
    registry = PieceRegistry()

    with pytest.raises(UnknownPieceIdError):
        registry.reactivate(Piece.from_token("wK", piece_id=42))


def test_promotion_replaces_attributes_without_releasing_identity():
    registry = PieceRegistry()
    pawn = registry.register(Piece.from_token("wP"))
    promoted = pawn.with_piece_type("Q")

    registry.replace_piece(pawn, promoted)
    registry.deactivate(promoted)
    registry.reactivate(promoted)

    with pytest.raises(DuplicatePieceIdError):
        registry.deactivate(pawn)
