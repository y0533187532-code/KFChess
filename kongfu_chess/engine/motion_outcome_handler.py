"""Resolve the domain effects of completed, interrupted, and airborne motions."""

try:
    from ..model.events import GameOverEvent, MoveCompletedEvent, PieceCapturedEvent
    from ..realtime.arrival_resolver import ArrivalResult, apply_arrival
    from ..realtime.collision import clear_motion_transit
    from ..rules import resolve_promotion_piece_type
    from .reasons import CompletionReason
except ImportError:
    from model.events import GameOverEvent, MoveCompletedEvent, PieceCapturedEvent
    from realtime.arrival_resolver import ArrivalResult, apply_arrival
    from realtime.collision import clear_motion_transit
    from rules import resolve_promotion_piece_type
    from engine.reasons import CompletionReason


class MotionOutcomeHandler:
    """Apply board and state changes after the arbiter resolves a motion."""

    def __init__(
        self,
        board,
        state,
        rule_engine,
        arbiter,
        settings,
        capture_service,
        promotion_policy=None,
        event_publisher=None,
    ):
        self._board = board
        self._state = state
        self._rule_engine = rule_engine
        self._arbiter = arbiter
        self._settings = settings
        self._capture_service = capture_service
        self._promotion_policy = promotion_policy
        self._event_publisher = event_publisher

    def clear_source_cell(self, from_row, from_col):
        self._board.clear_cell(from_row, from_col)

    def execute_move(self, move):
        to_row, to_col = move["to"]
        self.execute_move_to_cell(move, to_row, to_col)

    def execute_move_to_cell(self, move, to_row, to_col):
        from_row, from_col = move["from"]
        moving = self._board.get_cell(from_row, from_col)
        if moving is None:
            return

        moving_piece_id = moving.piece_id
        requested_to = move["to"]
        result = apply_arrival(
            self._board,
            from_row,
            from_col,
            to_row,
            to_col,
            move["color"],
            promotion_piece_type=self._resolve_promotion(moving, to_row),
            game_over_piece_type=self._settings.game_over_piece_type,
        )

        self._arbiter.clear_rest(moving_piece_id)
        self._start_rest_for_piece_at(to_row, to_col)
        capture_event = None
        if result.captured_piece is not None:
            points_awarded = self._capture_service.record(
                result.captured_piece, (to_row, to_col), move["color"]
            )
            self._cancel_motions_from(to_row, to_col)
            capture_event = self._capture_event(
                result.captured_piece,
                move["color"],
                (to_row, to_col),
                points_awarded,
            )
        game_over_event = None
        if result.king_captured:
            self._state.mark_game_over()
            game_over_event = GameOverEvent(
                winning_color=move["color"],
                captured_piece_id=result.captured_piece.piece_id,
            )

        self._publish_completed_move(
            moving_piece_id,
            (from_row, from_col),
            requested_to,
            (to_row, to_col),
            result,
        )
        self._publish_if_present(capture_event)
        self._publish_if_present(game_over_event)

    def execute_move_to_airborne_origin(self, move, to_row, to_col):
        self._board.clear_cell(to_row, to_col)
        self.execute_move_to_cell(move, to_row, to_col)

    def complete_jump(self, move):
        row, col = move["from"]
        jumper = move.get("piece")
        if jumper is None:
            return

        occupant = self._board.get_cell(row, col)
        if occupant is not None and occupant.piece_id == jumper.piece_id:
            self._start_rest_for_piece_at(row, col)
            self._publish_completed_jump(jumper, row, col)
            return

        capture_event = None
        if occupant is not None:
            captured = occupant
            points_awarded = self._capture_service.record(
                captured, (row, col), jumper.color
            )
            capture_event = self._capture_event(
                captured,
                jumper.color,
                (row, col),
                points_awarded,
            )
            self._board.clear_cell(row, col)

        self._board.restore_piece(row, col, jumper)
        self._start_rest_for_piece_at(row, col)
        self._publish_completed_jump(jumper, row, col)
        self._publish_if_present(capture_event)

    def complete_airborne_travel(self, move):
        """Land a detached traveller against the destination's current state."""
        piece = move.get("piece")
        if piece is None:
            return

        to_row, to_col = move["to"]
        occupant = self._board.get_cell(to_row, to_col)
        capture_event = None
        king_captured = False

        if occupant is not None:
            if occupant.color == piece.color:
                raise RuntimeError(
                    "A friendly piece occupied a reserved landing cell"
                )

            self._board.clear_cell(to_row, to_col)
            self._cancel_motions_from(to_row, to_col)
            points_awarded = self._capture_service.record(
                occupant,
                (to_row, to_col),
                piece.color,
            )
            capture_event = self._capture_event(
                occupant,
                piece.color,
                (to_row, to_col),
                points_awarded,
            )
            king_captured = (
                occupant.piece_type == self._settings.game_over_piece_type
                and occupant.color != piece.color
            )

        promotion_piece_type = self._resolve_promotion(piece, to_row)
        arrived_piece = self._board.restore_piece(
            to_row,
            to_col,
            piece,
            promotion_piece_type=promotion_piece_type,
        )
        self._start_rest_for_piece_at(to_row, to_col)

        result = ArrivalResult(
            captured_piece=occupant,
            king_captured=king_captured,
        )
        game_over_event = None
        if king_captured:
            self._state.mark_game_over()
            game_over_event = GameOverEvent(
                winning_color=piece.color,
                captured_piece_id=occupant.piece_id,
            )

        self._publish_completed_move(
            arrived_piece.piece_id,
            move["from"],
            move["to"],
            move["to"],
            result,
        )
        self._publish_if_present(capture_event)
        self._publish_if_present(game_over_event)

    def cancel_motion(self, motion, captured_at=None):
        clear_motion_transit(motion)
        from_row, from_col = motion["from"]
        piece = self._board.get_cell(from_row, from_col)
        if piece is not None and piece.color == motion["color"]:
            if captured_at is not None:
                cap_row, cap_col = captured_at
                self._arbiter.clear_rest(piece.piece_id)
                self._state.record_capture(piece, cap_row, cap_col)
            self._board.clear_cell(from_row, from_col)
        self._arbiter.remove_motion(motion)

    def _publish_completed_move(
        self, piece_id, from_pos, requested_to, actual_to, result
    ):
        arrived_piece = self._board.get_cell(*actual_to)
        if arrived_piece is None:
            return
        self._event_publisher.publish(
            MoveCompletedEvent(
                piece_id=piece_id,
                token=arrived_piece.token,
                from_pos=from_pos,
                requested_to=requested_to,
                actual_to=actual_to,
                reason=self._completion_reason(requested_to, actual_to, result),
            )
        )

    def _publish_completed_jump(self, jumper, row, col):
        position = (row, col)
        self._event_publisher.publish(
            MoveCompletedEvent(
                piece_id=jumper.piece_id,
                token=jumper.token,
                from_pos=position,
                requested_to=position,
                actual_to=position,
                reason=CompletionReason.JUMP,
            )
        )

    @staticmethod
    def _capture_event(captured_piece, capturing_color, position, points_awarded):
        return PieceCapturedEvent(
            captured_piece_id=captured_piece.piece_id,
            captured_token=captured_piece.token,
            capturing_color=capturing_color,
            position=position,
            points_awarded=points_awarded,
        )

    def _publish_if_present(self, event):
        if event is not None:
            self._event_publisher.publish(event)

    def _cancel_motions_from(self, row, col):
        for motion in list(self._arbiter.active_moves):
            if motion["from"] == (row, col):
                self.cancel_motion(motion, captured_at=(row, col))

    def _start_rest_for_piece_at(self, row, col):
        piece = self._board.get_cell(row, col)
        if piece is None:
            return
        rest_ms = self._settings.rest_duration_for(piece.piece_type)
        if rest_ms > 0:
            self._arbiter.start_rest(piece.piece_id, rest_ms)

    @staticmethod
    def _completion_reason(requested_to, actual_to, result):
        if result.captured_piece is not None:
            return CompletionReason.CAPTURE
        if actual_to != requested_to:
            return CompletionReason.SAME_COLOR_BLOCKED
        return CompletionReason.COMPLETED

    def _resolve_promotion(self, moving, to_row):
        chosen_type = self._state.promotion_choice
        if self._promotion_policy is None:
            promotion = resolve_promotion_piece_type(
                moving,
                to_row,
                self._board.num_rows,
                self._rule_engine.piece_rules,
                chosen_type=chosen_type,
            )
        else:
            promotion = self._promotion_policy(
                moving, to_row, self._board.num_rows, chosen_type=chosen_type
            )

        if promotion is not None:
            self._state.consume_promotion_choice()
        return promotion
