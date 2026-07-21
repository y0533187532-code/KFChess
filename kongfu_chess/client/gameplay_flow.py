"""Authoritative board commands, snapshot refresh, and lifecycle polling."""

from __future__ import annotations

from ..model.piece_state import PieceState
from ..protocol import (
    GameSnapshotPayloadError,
    MessageType,
    deserialize_game_snapshot,
)
from .ui_state import ClientScreen


class GameplayFlow:
    _TERMINAL_STATES = {"ENDED", "CANCELLED", "INTERRUPTED"}
    _LIFECYCLE_TYPES = {
        MessageType.GAME_LIFECYCLE_STATUS.value,
        MessageType.DISCONNECT_COUNTDOWN.value,
        MessageType.GAME_CANCELLED.value,
        MessageType.GAME_FORFEIT.value,
        MessageType.GAME_OVER.value,
    }

    def __init__(
        self,
        context,
        *,
        snapshot_poll_interval_ms: int,
        lifecycle_poll_interval_ms: int,
        active_snapshot_poll_interval_ms: int = 200,
    ):
        self._context = context
        self._snapshot_poll_interval_ms = snapshot_poll_interval_ms
        self._active_snapshot_poll_interval_ms = active_snapshot_poll_interval_ms
        self._lifecycle_poll_interval_ms = lifecycle_poll_interval_ms
        self._game_id: str | None = None
        self._snapshot_pending = False
        self._lifecycle_pending = False
        self._command_pending = False
        self._next_snapshot_poll_ms: int | None = None
        self._next_lifecycle_poll_ms: int | None = None
        self._last_push_ms: int | None = None
        self._push_quiet_ms: int = 500
        self._reconnect_pending = False

    def activate_if_ready(self) -> None:
        game = self._context.session.game
        if game is None or game.game_id == self._game_id:
            return
        room = self._context.session.room
        if game.mode == "ROOM" and (
            room is None
            or not room.gameplay_started
            or room.status != "ACTIVE"
        ):
            return
        self._reset_runtime_state()
        self._game_id = game.game_id
        self._context.state.game_lifecycle_state = "ACTIVE"
        self._submit_snapshot()
        if game.role == "PLAYER":
            self._submit_lifecycle_status()

    def bootstrap_room_snapshot(self, payload) -> None:
        if payload.get("role") != "SPECTATOR":
            return
        snapshot_payload = payload.get("snapshot")
        if snapshot_payload is None:
            return
        game = self._context.session.game
        if game is None:
            return
        try:
            snapshot = deserialize_game_snapshot(snapshot_payload)
        except GameSnapshotPayloadError:
            return
        self._game_id = game.game_id
        state = self._context.state
        state.game_snapshot = snapshot
        state.game_lifecycle_state = "ACTIVE"
        state.screen = ClientScreen.GAME_BOARD
        if "sequence" in snapshot_payload:
            state.game_sequence = int(snapshot_payload["sequence"])
        self._schedule_snapshot_poll()

    def tick(self, now_ms: int) -> None:
        if self._game_id is None:
            return
        state = self._context.state
        if state.screen is not ClientScreen.GAME_BOARD:
            return
        if (
            state.game_lifecycle_state == "ACTIVE"
            and not self._snapshot_pending
            and self._next_snapshot_poll_ms is not None
            and now_ms >= self._next_snapshot_poll_ms
        ):
            self._submit_snapshot()
        game = self._context.session.game
        if (
            game is not None
            and game.role == "PLAYER"
            and not self._lifecycle_pending
            and self._next_lifecycle_poll_ms is not None
            and now_ms >= self._next_lifecycle_poll_ms
        ):
            self._submit_lifecycle_status()

    def handle_board_cell(self, row: int, col: int) -> None:
        state = self._context.state
        game = self._context.session.game
        snapshot = state.game_snapshot
        if (
            state.screen is not ClientScreen.GAME_BOARD
            or game is None
            or snapshot is None
            or game.role != "PLAYER"
            or game.color is None
            or self._command_pending
        ):
            return
        if state.game_lifecycle_state != "ACTIVE":
            self._context.show_error("game_paused")
            return
        if not (
            0 <= row < snapshot.board_height
            and 0 <= col < snapshot.board_width
        ):
            return

        selected_piece = self._selected_piece(snapshot)
        clicked_piece = self._piece_at(snapshot, row, col)
        if selected_piece is None:
            if self._is_selectable(clicked_piece, game.color):
                state.game_selected_cell = (row, col)
                state.game_selected_piece_id = clicked_piece.piece_id
            else:
                self._clear_selection()
            return
        if self._is_selectable(clicked_piece, game.color) and (
            row,
            col,
        ) != state.game_selected_cell:
            state.game_selected_cell = (row, col)
            state.game_selected_piece_id = clicked_piece.piece_id
            return

        expected_from = (selected_piece.row, selected_piece.col)
        auth_token = self._context.session.require_auth_token()
        if (row, col) == expected_from:
            envelope = self._context.messages.jump(
                auth_token,
                game.game_token,
                game.game_id,
                selected_piece.piece_id,
                expected_from,
            )
            operation = "game_jump"
        else:
            envelope = self._context.messages.move(
                auth_token,
                game.game_token,
                game.game_id,
                selected_piece.piece_id,
                expected_from,
                (row, col),
            )
            operation = "game_move"
        self._command_pending = True
        self._clear_selection()
        self._context.submit(envelope, operation, show_loading=False)

    def handle_success(
        self, operation: str | None, message_type: str, payload
    ) -> bool:
        if (
            operation == "game_snapshot"
            and message_type == MessageType.SNAPSHOT.value
        ):
            self._snapshot_pending = False
            try:
                snapshot = deserialize_game_snapshot(payload)
            except GameSnapshotPayloadError:
                self._context.show_error("invalid_snapshot")
                self._schedule_snapshot_poll()
                return True
            self._context.state.game_snapshot = snapshot
            self._context.state.screen = ClientScreen.GAME_BOARD
            if "sequence" in payload:
                self._context.state.game_sequence = int(payload["sequence"])
            self._schedule_snapshot_poll()
            return True
        if operation in {"game_move", "game_jump"}:
            self._command_pending = False
            if payload.get("snapshot") is not None:
                self._apply_state_update(payload, from_push=False)
            else:
                self._submit_snapshot()
            return True
        if operation == "game_lifecycle" and message_type in self._LIFECYCLE_TYPES:
            self._lifecycle_pending = False
            self._handle_lifecycle(payload)
            return True
        if operation == "game_reconnect" and message_type in self._LIFECYCLE_TYPES:
            self._reconnect_pending = False
            self._handle_lifecycle(payload)
            self._submit_snapshot()
            return True
        return False

    def handle_push(self, payload) -> bool:
        if self._game_id is None:
            return False
        if str(payload.get("game_id")) != self._game_id:
            return False
        return self._apply_state_update(payload, from_push=True)

    def handle_lifecycle_push(self, message_type: str, payload) -> bool:
        if message_type not in self._LIFECYCLE_TYPES:
            return False
        if self._game_id is None:
            return False
        if str(payload.get("game_id")) != self._game_id:
            return False
        self._lifecycle_pending = False
        self._handle_lifecycle(payload)
        if message_type != MessageType.DISCONNECT_COUNTDOWN.value:
            self._submit_snapshot()
        return True

    def handle_network_loss(self) -> bool:
        game = self._context.session.game
        state = self._context.state
        if (
            game is None
            or game.role != "PLAYER"
            or state.screen is not ClientScreen.GAME_BOARD
            or state.game_lifecycle_state in self._TERMINAL_STATES
            or self._reconnect_pending
        ):
            return False
        self._reconnect_pending = True
        self._context.submit(
            self._context.messages.game_reconnect(
                self._context.session.require_auth_token(),
                game.game_token,
                game.game_id,
            ),
            "game_reconnect",
            show_loading=False,
        )
        return True

    def disconnect_active_game(self) -> None:
        game = self._context.session.game
        state = self._context.state
        if (
            game is None
            or game.role != "PLAYER"
            or state.game_lifecycle_state in self._TERMINAL_STATES
        ):
            return
        try:
            self._context.dispatcher.send_immediate(
                self._context.messages.game_disconnect(
                    self._context.session.require_auth_token(),
                    game.game_token,
                    game.game_id,
                )
            )
        except OSError:
            return

    def stop_room_runtime(self) -> None:
        self._stop()

    def _apply_state_update(self, payload, *, from_push: bool) -> bool:
        sequence = payload.get("sequence")
        snapshot_payload = payload.get("snapshot")
        if snapshot_payload is None:
            if from_push:
                self._submit_snapshot()
            return from_push

        state = self._context.state
        if sequence is not None:
            current = state.game_sequence
            incoming = int(sequence)
            if current is not None:
                if incoming <= current:
                    return True
                if incoming > current + 1:
                    self._submit_snapshot()
                    return True
            state.game_sequence = incoming

        try:
            snapshot = deserialize_game_snapshot(snapshot_payload)
        except GameSnapshotPayloadError:
            self._context.show_error("invalid_snapshot")
            self._schedule_snapshot_poll()
            return True

        state.game_snapshot = snapshot
        state.screen = ClientScreen.GAME_BOARD
        if from_push:
            self._last_push_ms = state.now_ms
        self._schedule_snapshot_poll()
        return True

    def handle_failure(self, operation: str | None, code: str) -> bool:
        if operation == "game_snapshot":
            self._snapshot_pending = False
            self._schedule_snapshot_poll()
        elif operation == "game_lifecycle":
            self._lifecycle_pending = False
            self._schedule_lifecycle_poll()
        elif operation in {"game_move", "game_jump"}:
            self._command_pending = False
            self._clear_selection()
            if code == "stale_client_state":
                self._submit_snapshot()
        elif operation == "game_reconnect":
            self._reconnect_pending = False
        else:
            return False
        self._context.show_error(code)
        return True

    def _submit_snapshot(self) -> None:
        game = self._context.session.game
        if game is None or self._snapshot_pending:
            return
        self._snapshot_pending = True
        self._context.submit(
            self._context.messages.resync(
                self._context.session.require_auth_token(),
                game.game_token,
                game.game_id,
            ),
            "game_snapshot",
            show_loading=False,
        )

    def _submit_lifecycle_status(self) -> None:
        game = self._context.session.game
        if game is None or self._lifecycle_pending:
            return
        self._lifecycle_pending = True
        self._context.submit(
            self._context.messages.lifecycle_status(
                self._context.session.require_auth_token(),
                game.game_token,
                game.game_id,
            ),
            "game_lifecycle",
            show_loading=False,
        )

    def _handle_lifecycle(self, payload) -> None:
        lifecycle_state = str(payload["state"])
        state = self._context.state
        state.game_lifecycle_state = lifecycle_state
        deadline = payload.get("reconnect_deadline_ms")
        state.game_reconnect_deadline_ms = (
            None if deadline is None else int(deadline)
        )
        if lifecycle_state in self._TERMINAL_STATES:
            self._finish(lifecycle_state, payload)
            return
        if lifecycle_state == "ACTIVE":
            state.game_reconnect_deadline_ms = None
            self._schedule_snapshot_poll()
        self._schedule_lifecycle_poll()

    def _finish(self, lifecycle_state: str, payload) -> None:
        game = self._context.session.game
        if game is None:
            return
        message_key = self._outcome_message(lifecycle_state, payload, game.seat)
        mode = game.mode
        self._stop()
        self._context.session.clear_game()
        if mode == "ROOM" and self._context.session.room is not None:
            room_status = {
                "ENDED": "ENDED",
                "CANCELLED": "CLOSED",
                "INTERRUPTED": "INTERRUPTED",
            }[lifecycle_state]
            self._context.session.update_room_status(
                room_status, gameplay_started=False
            )
            self._context.show(ClientScreen.ROOM_LOBBY)
        else:
            self._context.show(ClientScreen.MAIN_MENU)
        self._context.show_message(message_key)

    @staticmethod
    def _outcome_message(lifecycle_state: str, payload, own_seat: str | None) -> str:
        if lifecycle_state == "CANCELLED":
            return "game_cancelled_message"
        if lifecycle_state == "INTERRUPTED":
            return "game_interrupted_message"
        winner = payload.get("winner_seat")
        if winner is None or own_seat is None:
            return "game_ended_message"
        return "game_won_message" if winner == own_seat else "game_lost_message"

    def _selected_piece(self, snapshot):
        piece_id = self._context.state.game_selected_piece_id
        selected_cell = self._context.state.game_selected_cell
        if piece_id is None or selected_cell is None:
            return None
        piece = next(
            (item for item in snapshot.pieces if item.piece_id == piece_id),
            None,
        )
        if piece is None or (piece.row, piece.col) != selected_cell:
            self._clear_selection()
            return None
        return piece

    @staticmethod
    def _piece_at(snapshot, row: int, col: int):
        return next(
            (
                piece
                for piece in snapshot.pieces
                if (piece.row, piece.col) == (row, col)
                and piece.state != PieceState.CAPTURED
            ),
            None,
        )

    @staticmethod
    def _is_selectable(piece, color: str) -> bool:
        return piece is not None and piece.token.startswith(color)

    def _clear_selection(self) -> None:
        self._context.state.game_selected_cell = None
        self._context.state.game_selected_piece_id = None

    def _schedule_snapshot_poll(self) -> None:
        interval = self._snapshot_poll_interval_ms
        if self._context.state.game_lifecycle_state == "ACTIVE":
            snapshot = self._context.state.game_snapshot
            if snapshot is not None and self._snapshot_needs_fast_poll(snapshot):
                interval = self._active_snapshot_poll_interval_ms
        now_ms = self._context.state.now_ms
        if self._last_push_ms is not None:
            quiet_until = self._last_push_ms + self._push_quiet_ms
            if now_ms < quiet_until:
                interval = max(interval, quiet_until - now_ms)
        self._next_snapshot_poll_ms = now_ms + interval

    @staticmethod
    def _snapshot_needs_fast_poll(snapshot) -> bool:
        if snapshot.active_motions:
            return True
        return any(
            piece.rest_remaining_ms is not None and piece.rest_remaining_ms > 0
            for piece in snapshot.pieces
        )

    def _schedule_lifecycle_poll(self) -> None:
        self._next_lifecycle_poll_ms = (
            self._context.state.now_ms + self._lifecycle_poll_interval_ms
        )

    def _reset_runtime_state(self) -> None:
        self._snapshot_pending = False
        self._lifecycle_pending = False
        self._command_pending = False
        self._reconnect_pending = False
        self._next_snapshot_poll_ms = None
        self._next_lifecycle_poll_ms = None
        state = self._context.state
        state.game_snapshot = None
        state.game_sequence = None
        state.game_lifecycle_state = None
        state.game_reconnect_deadline_ms = None
        self._clear_selection()

    def _stop(self) -> None:
        self._game_id = None
        self._reset_runtime_state()
