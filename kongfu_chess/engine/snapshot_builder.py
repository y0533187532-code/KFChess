"""Build immutable read models from the mutable game domain."""

from __future__ import annotations

try:
    from ..model.piece import (
        PIECE_STATE_CAPTURED,
        PIECE_STATE_JUMPING,
        PIECE_STATE_MOVING,
        PIECE_STATE_RESTING,
    )
    from .types import GameSnapshot, MoveEventSnapshot, PieceSnapshot
except ImportError:
    from model.piece import (
        PIECE_STATE_CAPTURED,
        PIECE_STATE_JUMPING,
        PIECE_STATE_MOVING,
        PIECE_STATE_RESTING,
    )
    from engine.types import GameSnapshot, MoveEventSnapshot, PieceSnapshot


class SnapshotBuilder:
    """Projects board, state, rules, and motion into a renderer-facing DTO."""

    def __init__(self, board, state, rule_engine, arbiter):
        self._board = board
        self._state = state
        self._rule_engine = rule_engine
        self._arbiter = arbiter

    def build(self) -> GameSnapshot:
        moving_origins = self._arbiter.moving_origins()
        pieces = list(self._board_piece_snapshots(moving_origins))
        pieces.extend(self._airborne_piece_snapshots())
        pieces.extend(self._captured_piece_snapshots())
        return GameSnapshot(
            board_width=self._board.num_cols,
            board_height=self._board.num_rows,
            game_over=self._state.is_game_over,
            selected=self._state.selected,
            pieces=tuple(pieces),
            legal_destinations=self._legal_destinations(),
            score_by_color=self._state.score_by_color,
            completed_moves=tuple(
                MoveEventSnapshot(
                    piece_id=event.piece_id,
                    token=event.token,
                    from_pos=event.from_pos,
                    requested_to=event.requested_to,
                    actual_to=event.actual_to,
                    reason=event.reason,
                )
                for event in self._state.move_history.events
            ),
        )

    def _board_piece_snapshots(self, moving_origins):
        airborne_piece_ids = {
            move["piece"].piece_id
            for move in self._arbiter.active_moves
            if move.get("jump") and move.get("piece") is not None
        }
        for row in range(self._board.num_rows):
            for col in range(self._board.num_cols):
                piece = self._board.get_cell(row, col)
                if piece is None or piece.piece_id in airborne_piece_ids:
                    continue
                yield self._piece_snapshot(piece, row, col, moving_origins)

    def _piece_snapshot(self, piece, row, col, moving_origins):
        motion = self._active_motion_from(row, col, piece.piece_id)
        rest_remaining_ms = self._arbiter.rest_remaining_ms(piece.piece_id)
        if motion is not None:
            state = PIECE_STATE_JUMPING if motion.get("jump") else PIECE_STATE_MOVING
            rest_remaining_ms = None
        elif rest_remaining_ms is not None:
            state = PIECE_STATE_RESTING
        else:
            state = piece.state
        if (row, col) in moving_origins:
            rest_remaining_ms = None
        return PieceSnapshot(
            row=row,
            col=col,
            token=piece.token,
            piece_id=piece.piece_id,
            state=state,
            rest_remaining_ms=rest_remaining_ms,
        )

    def _airborne_piece_snapshots(self):
        for move in self._arbiter.active_moves:
            jump_piece = move.get("piece")
            if not move.get("jump") or jump_piece is None:
                continue
            row, col = move["from"]
            yield PieceSnapshot(
                row=row,
                col=col,
                token=jump_piece.token,
                piece_id=jump_piece.piece_id,
                state=PIECE_STATE_JUMPING,
                rest_remaining_ms=None,
            )

    def _captured_piece_snapshots(self):
        for captured_piece in self._state.captured_pieces:
            yield PieceSnapshot(
                row=captured_piece.row,
                col=captured_piece.col,
                token=captured_piece.token,
                piece_id=captured_piece.piece_id,
                state=PIECE_STATE_CAPTURED,
            )

    def _active_motion_from(self, row, col, piece_id):
        for motion in self._arbiter.active_moves:
            moving_piece = motion.get("piece")
            if moving_piece is not None and moving_piece.piece_id != piece_id:
                continue
            if motion["from"] == (row, col):
                return motion
        return None

    def _legal_destinations(self):
        selected = self._state.selected
        if selected is None:
            return ()
        row, col = selected
        piece = self._board.get_cell(row, col)
        if piece is None or (row, col) in self._arbiter.moving_origins():
            return ()
        if self._arbiter.is_piece_resting(piece.piece_id):
            return ()
        destinations = self._rule_engine.piece_rules.legal_destinations(
            self._board, piece, row, col
        )
        return tuple(sorted((position.row, position.col) for position in destinations))
