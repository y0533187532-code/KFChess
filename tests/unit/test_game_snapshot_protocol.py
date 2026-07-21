import pytest

from kongfu_chess.engine import (
    GameSnapshot,
    MotionSnapshot,
    MoveEventSnapshot,
    PieceSnapshot,
)
from kongfu_chess.model.piece_state import PieceState
from kongfu_chess.protocol import (
    GameSnapshotPayloadError,
    deserialize_game_snapshot,
    serialize_game_snapshot,
)


def authoritative_snapshot():
    return GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        selected=(6, 0),
        pieces=(
            PieceSnapshot(6, 0, "wP", 7, PieceState.RESTING, 250),
            PieceSnapshot(1, 0, "bP", 8),
        ),
        legal_destinations=((5, 0),),
        score_by_color={"w": 1, "b": 0},
        completed_moves=(
            MoveEventSnapshot(7, "wP", (6, 0), (5, 0), (5, 0), "arrived"),
        ),
        active_motions=(
            MotionSnapshot((1, 0), (2, 0), 500, 1000, 3, piece_id=8),
        ),
        elapsed_ms=1500,
    )


def test_snapshot_json_contract_round_trips_complete_authoritative_dto():
    snapshot = authoritative_snapshot()

    payload = serialize_game_snapshot(snapshot)
    restored = deserialize_game_snapshot(payload)

    assert restored == snapshot
    assert payload["pieces"][0]["state"] == "resting"
    assert payload["active_motions"][0]["from_pos"] == [1, 0]


def test_snapshot_json_contract_rejects_missing_or_invalid_fields():
    payload = serialize_game_snapshot(authoritative_snapshot())
    payload.pop("pieces")
    with pytest.raises(GameSnapshotPayloadError, match="schema"):
        deserialize_game_snapshot(payload)

    payload = serialize_game_snapshot(authoritative_snapshot())
    payload["pieces"][0]["state"] = "teleporting"
    with pytest.raises(GameSnapshotPayloadError, match="piece state"):
        deserialize_game_snapshot(payload)
