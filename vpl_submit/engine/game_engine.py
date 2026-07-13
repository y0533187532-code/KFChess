"""Application-service command boundary for move requests and time.

Parallel movement policy: multiple *different* pieces may travel at once.
The same piece cannot receive a second move or jump while it already has active
motion (``piece_in_motion``). Other conflicts are rejected by ``is_route_conflict``.
Arrival order, swap cancellation, and airborne jump capture are resolved by
RealTimeArbiter.

Airborne jump (conflict #4): same-cell re-click or ``jump`` command schedules
a jump via ``RealTimeArbiter.schedule_jump``; capture-on-arrival to an airborne
cell is handled in ``realtime.airborne_jump``.
"""

try:
    from ..config import (
        DEFAULT_JUMP_DURATION_MS,
        DEFAULT_MOVE_DURATION_MS,
        KING_PIECE_TYPE,
    )
    from ..engine.types import GameSnapshot, MoveResult, PieceSnapshot
    from ..model.piece import PIECE_STATE_CAPTURED, PIECE_STATE_MOVING
    from ..realtime import RealTimeArbiter
    from ..realtime.arrival_resolver import apply_arrival
    from ..rules import (
        RuleEngine,
        get_move_route,
        is_route_conflict,
        is_swap_route,
        resolve_promotion_piece_type,
    )
except ImportError:
    from config import (
        DEFAULT_JUMP_DURATION_MS,
        DEFAULT_MOVE_DURATION_MS,
        KING_PIECE_TYPE,
    )
    from engine.types import GameSnapshot, MoveResult, PieceSnapshot
    from model.piece import PIECE_STATE_CAPTURED, PIECE_STATE_MOVING
    from realtime import RealTimeArbiter
    from realtime.arrival_resolver import apply_arrival
    from rules import (
        RuleEngine,
        get_move_route,
        is_route_conflict,
        is_swap_route,
        resolve_promotion_piece_type,
    )


def default_promotion_policy(
    moving_piece, to_row, num_rows, piece_rules, chosen_type=None
):
    return resolve_promotion_piece_type(
        moving_piece,
        to_row,
        num_rows,
        piece_rules,
        chosen_type=chosen_type,
    )


class GameEngine:
    """Coordinates validation, motion scheduling, and arrival resolution."""

    def __init__(
        self,
        board,
        state,
        rule_engine=None,
        arbiter=None,
        move_durations=None,
        jump_duration_ms=None,
        promotion_policy=None,
        game_over_piece_type=None,
    ):
        self._board = board
        self._state = state
        self._rule_engine = rule_engine or RuleEngine()
        self._move_durations = dict(
            move_durations if move_durations is not None else DEFAULT_MOVE_DURATION_MS
        )
        self._jump_duration_ms = (
            jump_duration_ms
            if jump_duration_ms is not None
            else DEFAULT_JUMP_DURATION_MS
        )
        self._promotion_policy = promotion_policy or default_promotion_policy
        self._uses_default_promotion_policy = promotion_policy is None
        self._game_over_piece_type = (
            game_over_piece_type
            if game_over_piece_type is not None
            else KING_PIECE_TYPE
        )
        self._arbiter = arbiter or RealTimeArbiter(self)

    @property
    def board(self):
        return self._board

    @property
    def state(self):
        return self._state

    @property
    def rule_engine(self):
        return self._rule_engine

    @property
    def arbiter(self):
        return self._arbiter

    @property
    def active_moves(self):
        return self._arbiter.active_moves

    def moving_origins(self):
        return self._arbiter.moving_origins()

    def has_active_motion(self):
        return self._arbiter.has_active_motion()

    def request_move(self, from_row, from_col, to_row, to_col):
        if self._state.is_game_over:
            return MoveResult(is_accepted=False, reason="game_over")

        if (from_row, from_col) in self.moving_origins():
            return MoveResult(is_accepted=False, reason="piece_in_motion")

        validation = self._rule_engine.validate_move(
            self._board, from_row, from_col, to_row, to_col
        )
        if not validation.is_valid:
            return MoveResult(is_accepted=False, reason=validation.reason)

        piece = self._board.get_cell(from_row, from_col)
        new_route = get_move_route(from_row, from_col, to_row, to_col, piece.piece_type)
        new_from = (from_row, from_col)
        new_to = (to_row, to_col)

        for existing in self.active_moves:
            if is_route_conflict(
                existing["from"],
                existing["to"],
                existing["route"],
                new_from,
                new_to,
                new_route,
                existing["color"],
                piece.color,
                existing_jump=existing.get("jump", False),
            ):
                return MoveResult(is_accepted=False, reason="route_conflict")

        self._arbiter.schedule_travel(
            new_from,
            new_to,
            self._move_durations[piece.piece_type] * len(new_route),
            new_route,
            piece.color,
        )
        return MoveResult(is_accepted=True, reason="ok")

    def request_jump(self, from_row, from_col):
        if self._state.is_game_over:
            return MoveResult(is_accepted=False, reason="game_over")

        if (from_row, from_col) in self.moving_origins():
            return MoveResult(is_accepted=False, reason="piece_in_motion")

        piece = self._board.get_cell(from_row, from_col)
        if piece is None:
            return MoveResult(is_accepted=False, reason="empty_source")

        self._arbiter.schedule_jump(
            (from_row, from_col),
            self._jump_duration_ms,
            piece.color,
        )
        return MoveResult(is_accepted=True, reason="ok")

    def wait(self, milliseconds):
        """Advance simulated time and resolve arrivals."""
        self._arbiter.advance_time(milliseconds)

    def snapshot(self):
        moving_origins = self.moving_origins()
        pieces = []
        for row in range(self._board.num_rows):
            for col in range(self._board.num_cols):
                piece = self._board.get_cell(row, col)
                if piece is not None:
                    state = (
                        PIECE_STATE_MOVING
                        if (row, col) in moving_origins
                        else piece.state
                    )
                    pieces.append(
                        PieceSnapshot(
                            row=row,
                            col=col,
                            token=piece.token,
                            piece_id=piece.piece_id,
                            state=state,
                        )
                    )
        for piece, row, col in self._state.captured_pieces:
            pieces.append(
                PieceSnapshot(
                    row=row,
                    col=col,
                    token=piece.token,
                    piece_id=piece.piece_id,
                    state=PIECE_STATE_CAPTURED,
                )
            )
        return GameSnapshot(
            board_width=self._board.num_cols,
            board_height=self._board.num_rows,
            game_over=self._state.is_game_over,
            selected=self._state.selected,
            pieces=tuple(pieces),
        )

    def clear_source_cell(self, from_row, from_col):
        self._board.clear_cell(from_row, from_col)

    def execute_move(self, move):
        from_row, from_col = move["from"]
        to_row, to_col = move["to"]
        moving = self._board.get_cell(from_row, from_col)
        promotion = self._resolve_promotion(moving, to_row)
        result = apply_arrival(
            self._board,
            from_row,
            from_col,
            to_row,
            to_col,
            move["color"],
            promotion_piece_type=promotion,
            game_over_piece_type=self._game_over_piece_type,
        )
        if result.captured_piece is not None:
            self._state.record_capture(result.captured_piece, to_row, to_col)
        if result.king_captured:
            self._state.mark_game_over()

    def can_execute_move(self, move, completed_moves):
        for other in self.active_moves:
            if other is move:
                continue
            if self._is_swap_with_lower_order(move, other):
                return False

        for other in completed_moves:
            if self._is_swap_with_lower_order(move, other):
                return False

        return True

    def _resolve_promotion(self, moving, to_row):
        chosen_type = self._state.promotion_choice
        piece_rules = self._rule_engine.piece_rules
        if self._uses_default_promotion_policy:
            promotion = resolve_promotion_piece_type(
                moving,
                to_row,
                self._board.num_rows,
                piece_rules,
                chosen_type=chosen_type,
            )
        else:
            promotion = self._promotion_policy(
                moving, to_row, self._board.num_rows, chosen_type=chosen_type
            )

        if promotion is not None:
            self._state.consume_promotion_choice()
        return promotion

    def _is_swap_with_lower_order(self, move, other):
        return (
            is_swap_route(
                move["from"],
                move["to"],
                move["color"],
                other["from"],
                other["to"],
                other["color"],
            )
            and other["order"] < move["order"]
        )
