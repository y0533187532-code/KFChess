"""Application-service command boundary for move requests and time.

Parallel movement policy: multiple *different* pieces may travel at once.
The same piece cannot receive a second move or jump while it already has active
motion (``piece_in_motion``). Timed cell-entry collisions are resolved by
RealTimeArbiter (enemy later-capture, same-color early stop).

Airborne jump (conflict #4): same-cell re-click or ``jump`` command schedules
a jump via ``RealTimeArbiter.schedule_jump``; origin occupancy uses the same
timed collision rules as travel.
"""

try:
    from ..engine.capture_service import CaptureService, MaterialScorePolicy
    from ..engine.event_bus import SynchronousEventBus
    from ..engine.motion_outcome_handler import MotionOutcomeHandler
    from ..engine.reasons import MoveReason
    from ..engine.settings import EngineSettings
    from ..engine.snapshot_builder import SnapshotBuilder
    from ..engine.types import MoveResult
    from ..model.events import MoveCompletedEvent
    from ..realtime import RealTimeArbiter
    from ..rules import (
        RuleEngine,
        get_move_route,
        resolve_promotion_piece_type,
    )
except ImportError:
    from engine.capture_service import CaptureService, MaterialScorePolicy
    from engine.event_bus import SynchronousEventBus
    from engine.motion_outcome_handler import MotionOutcomeHandler
    from engine.reasons import MoveReason
    from engine.settings import EngineSettings
    from engine.snapshot_builder import SnapshotBuilder
    from engine.types import MoveResult
    from model.events import MoveCompletedEvent
    from realtime import RealTimeArbiter
    from rules import (
        RuleEngine,
        get_move_route,
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
    """Coordinate action requests, motion scheduling, and engine read APIs."""

    def __init__(
        self,
        board,
        state,
        rule_engine=None,
        arbiter=None,
        move_durations=None,
        jump_duration_ms=None,
        rest_durations=None,
        promotion_policy=None,
        game_over_piece_type=None,
        score_policy=None,
        settings=None,
        snapshot_builder=None,
        arbiter_factory=None,
        motion_outcomes=None,
        event_bus=None,
    ):
        self._board = board
        self._state = state
        self._rule_engine = rule_engine or RuleEngine()
        if settings is not None and any(
            value is not None
            for value in (
                move_durations,
                jump_duration_ms,
                rest_durations,
                game_over_piece_type,
            )
        ):
            raise ValueError(
                "Pass either EngineSettings or individual setting overrides, not both"
            )
        self._settings = settings or EngineSettings.from_overrides(
            move_durations=move_durations,
            jump_duration_ms=jump_duration_ms,
            rest_durations=rest_durations,
            game_over_piece_type=game_over_piece_type,
        )
        arbiter_type = arbiter_factory or RealTimeArbiter
        self._arbiter = arbiter or arbiter_type(self)
        self._event_bus = event_bus or SynchronousEventBus()
        self._event_bus.subscribe(MoveCompletedEvent, state.move_history)
        self._capture_service = CaptureService(
            state,
            self._arbiter,
            score_policy or MaterialScorePolicy(),
        )
        self._snapshot_builder = snapshot_builder or SnapshotBuilder(
            board, state, self._rule_engine, self._arbiter
        )
        self._motion_outcomes = motion_outcomes or MotionOutcomeHandler(
            board,
            state,
            self._rule_engine,
            self._arbiter,
            self._settings,
            self._capture_service,
            promotion_policy=promotion_policy,
            event_publisher=self._event_bus,
        )

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
    def settings(self):
        return self._settings

    @property
    def active_moves(self):
        return self._arbiter.active_moves

    def moving_origins(self):
        return self._arbiter.moving_origins()

    def has_active_motion(self):
        return self._arbiter.has_active_motion()

    def is_piece_resting_at(self, row, col):
        piece = self._board.get_cell(row, col)
        if piece is None:
            return False
        return self._arbiter.is_piece_resting(piece.piece_id)

    def request_move(self, from_row, from_col, to_row, to_col):
        if self._state.is_game_over:
            return MoveResult(is_accepted=False, reason=MoveReason.GAME_OVER)

        if (from_row, from_col) in self.moving_origins():
            return MoveResult(is_accepted=False, reason=MoveReason.PIECE_IN_MOTION)

        if self.is_piece_resting_at(from_row, from_col):
            return MoveResult(is_accepted=False, reason=MoveReason.PIECE_RESTING)

        validation = self._rule_engine.validate_move(
            self._board, from_row, from_col, to_row, to_col
        )
        if not validation.is_valid:
            return MoveResult(is_accepted=False, reason=validation.reason)

        piece = self._board.get_cell(from_row, from_col)
        new_route = get_move_route(from_row, from_col, to_row, to_col, piece.piece_type)
        new_from = (from_row, from_col)

        self._arbiter.schedule_travel(
            new_from,
            (to_row, to_col),
            self._settings.move_duration_for(piece.piece_type) * len(new_route),
            new_route,
            piece.color,
        )
        return MoveResult(is_accepted=True, reason=MoveReason.OK)

    def request_jump(self, from_row, from_col):
        if self._state.is_game_over:
            return MoveResult(is_accepted=False, reason=MoveReason.GAME_OVER)

        if (from_row, from_col) in self.moving_origins():
            return MoveResult(is_accepted=False, reason=MoveReason.PIECE_IN_MOTION)

        if self.is_piece_resting_at(from_row, from_col):
            return MoveResult(is_accepted=False, reason=MoveReason.PIECE_RESTING)

        piece = self._board.get_cell(from_row, from_col)
        if piece is None:
            return MoveResult(is_accepted=False, reason=MoveReason.EMPTY_SOURCE)

        self._arbiter.schedule_jump(
            (from_row, from_col),
            self._settings.jump_duration_ms,
            piece.color,
            piece,
        )
        return MoveResult(is_accepted=True, reason=MoveReason.OK)

    def wait(self, milliseconds):
        """Advance simulated time and resolve arrivals."""
        self._arbiter.advance_time(milliseconds)

    def snapshot(self):
        return self._snapshot_builder.build()

    def subscribe(self, event_type, subscriber):
        self._event_bus.subscribe(event_type, subscriber)

    def unsubscribe(self, event_type, subscriber):
        self._event_bus.unsubscribe(event_type, subscriber)

    def clear_source_cell(self, from_row, from_col):
        self._motion_outcomes.clear_source_cell(from_row, from_col)

    def execute_move(self, move):
        self._motion_outcomes.execute_move(move)

    def execute_move_to_cell(self, move, to_row, to_col):
        self._motion_outcomes.execute_move_to_cell(move, to_row, to_col)

    def execute_move_to_airborne_origin(self, move, to_row, to_col):
        self._motion_outcomes.execute_move_to_airborne_origin(move, to_row, to_col)

    def complete_jump(self, move):
        self._motion_outcomes.complete_jump(move)

    def cancel_motion(self, motion, captured_at=None):
        self._motion_outcomes.cancel_motion(motion, captured_at=captured_at)
