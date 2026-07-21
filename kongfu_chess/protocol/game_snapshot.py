"""JSON boundary mapping for the authoritative engine snapshot DTO."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum

from ..engine import GameSnapshot, MotionSnapshot, MoveEventSnapshot, PieceSnapshot
from ..model.piece_state import PieceState


class GameSnapshotPayloadError(ValueError):
    """Raised when a network snapshot does not match the shared contract."""


def serialize_game_snapshot(snapshot: GameSnapshot) -> dict:
    """Return the complete JSON-safe representation of ``GameSnapshot``."""

    return {
        "board_width": snapshot.board_width,
        "board_height": snapshot.board_height,
        "game_over": snapshot.game_over,
        "selected": _serialize_coordinate(snapshot.selected),
        "pieces": [
            {
                "row": piece.row,
                "col": piece.col,
                "token": piece.token,
                "piece_id": piece.piece_id,
                "state": _enum_value(piece.state),
                "rest_remaining_ms": piece.rest_remaining_ms,
            }
            for piece in snapshot.pieces
        ],
        "legal_destinations": [
            _serialize_coordinate(coordinate)
            for coordinate in snapshot.legal_destinations
        ],
        "score_by_color": dict(snapshot.score_by_color),
        "completed_moves": [
            {
                "piece_id": move.piece_id,
                "token": move.token,
                "from_pos": _serialize_coordinate(move.from_pos),
                "requested_to": _serialize_coordinate(move.requested_to),
                "actual_to": _serialize_coordinate(move.actual_to),
                "reason": _enum_value(move.reason),
            }
            for move in snapshot.completed_moves
        ],
        "active_motions": [
            {
                "from_pos": _serialize_coordinate(motion.from_pos),
                "to_pos": _serialize_coordinate(motion.to_pos),
                "remaining_ms": motion.remaining_ms,
                "total_ms": motion.total_ms,
                "order": motion.order,
                "is_jump": motion.is_jump,
                "piece_id": motion.piece_id,
            }
            for motion in snapshot.active_motions
        ],
        "elapsed_ms": snapshot.elapsed_ms,
    }


def deserialize_game_snapshot(payload: Mapping) -> GameSnapshot:
    """Validate and rebuild the immutable snapshot used by client renderers."""

    expected_fields = {
        "board_width",
        "board_height",
        "game_over",
        "selected",
        "pieces",
        "legal_destinations",
        "score_by_color",
        "completed_moves",
        "active_motions",
        "elapsed_ms",
    }
    _require_mapping_fields(payload, expected_fields, "snapshot")
    selected = payload["selected"]
    return GameSnapshot(
        board_width=_non_negative_int(payload["board_width"], "board_width"),
        board_height=_non_negative_int(payload["board_height"], "board_height"),
        game_over=_boolean(payload["game_over"], "game_over"),
        selected=(
            None if selected is None else _coordinate(selected, "selected")
        ),
        pieces=tuple(_piece(item) for item in _sequence(payload["pieces"], "pieces")),
        legal_destinations=tuple(
            _coordinate(item, "legal_destinations")
            for item in _sequence(
                payload["legal_destinations"], "legal_destinations"
            )
        ),
        score_by_color=_scores(payload["score_by_color"]),
        completed_moves=tuple(
            _completed_move(item)
            for item in _sequence(payload["completed_moves"], "completed_moves")
        ),
        active_motions=tuple(
            _motion(item)
            for item in _sequence(payload["active_motions"], "active_motions")
        ),
        elapsed_ms=_non_negative_int(payload["elapsed_ms"], "elapsed_ms"),
    )


def _piece(value) -> PieceSnapshot:
    fields = {"row", "col", "token", "piece_id", "state", "rest_remaining_ms"}
    _require_mapping_fields(value, fields, "piece")
    state_value = _non_empty_string(value["state"], "state")
    try:
        state = PieceState(state_value)
    except ValueError as exc:
        raise GameSnapshotPayloadError("Invalid piece state") from exc
    remaining = value["rest_remaining_ms"]
    return PieceSnapshot(
        row=_non_negative_int(value["row"], "row"),
        col=_non_negative_int(value["col"], "col"),
        token=_non_empty_string(value["token"], "token"),
        piece_id=_non_negative_int(value["piece_id"], "piece_id"),
        state=state,
        rest_remaining_ms=(
            None
            if remaining is None
            else _non_negative_int(remaining, "rest_remaining_ms")
        ),
    )


def _completed_move(value) -> MoveEventSnapshot:
    fields = {
        "piece_id",
        "token",
        "from_pos",
        "requested_to",
        "actual_to",
        "reason",
    }
    _require_mapping_fields(value, fields, "completed move")
    return MoveEventSnapshot(
        piece_id=_non_negative_int(value["piece_id"], "piece_id"),
        token=_non_empty_string(value["token"], "token"),
        from_pos=_coordinate(value["from_pos"], "from_pos"),
        requested_to=_coordinate(value["requested_to"], "requested_to"),
        actual_to=_coordinate(value["actual_to"], "actual_to"),
        reason=_non_empty_string(value["reason"], "reason"),
    )


def _motion(value) -> MotionSnapshot:
    fields = {
        "from_pos",
        "to_pos",
        "remaining_ms",
        "total_ms",
        "order",
        "is_jump",
        "piece_id",
    }
    _require_mapping_fields(value, fields, "motion")
    piece_id = value["piece_id"]
    return MotionSnapshot(
        from_pos=_coordinate(value["from_pos"], "from_pos"),
        to_pos=_coordinate(value["to_pos"], "to_pos"),
        remaining_ms=_non_negative_int(value["remaining_ms"], "remaining_ms"),
        total_ms=_non_negative_int(value["total_ms"], "total_ms"),
        order=_non_negative_int(value["order"], "order"),
        is_jump=_boolean(value["is_jump"], "is_jump"),
        piece_id=(
            None
            if piece_id is None
            else _non_negative_int(piece_id, "piece_id")
        ),
    )


def _scores(value) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise GameSnapshotPayloadError("score_by_color must be an object")
    scores = {}
    for color, score in value.items():
        scores[_non_empty_string(color, "color")] = _non_negative_int(
            score, "score"
        )
    return scores


def _coordinate(value, field_name: str) -> tuple[int, int]:
    values = _sequence(value, field_name)
    if len(values) != 2:
        raise GameSnapshotPayloadError(f"{field_name} must have two values")
    return (
        _non_negative_int(values[0], field_name),
        _non_negative_int(values[1], field_name),
    )


def _serialize_coordinate(value):
    return None if value is None else [value[0], value[1]]


def _require_mapping_fields(value, fields: set[str], description: str) -> None:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise GameSnapshotPayloadError(
            f"Serialized {description} does not match its schema"
        )


def _sequence(value, field_name: str) -> Sequence:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise GameSnapshotPayloadError(f"{field_name} must be an array")
    return value


def _non_negative_int(value, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GameSnapshotPayloadError(
            f"{field_name} must be a non-negative integer"
        )
    return value


def _boolean(value, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise GameSnapshotPayloadError(f"{field_name} must be a boolean")
    return value


def _non_empty_string(value, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise GameSnapshotPayloadError(f"{field_name} must be a non-empty string")
    return value


def _enum_value(value) -> str:
    return str(value.value) if isinstance(value, Enum) else str(value)
