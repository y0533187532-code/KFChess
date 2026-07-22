"""Idempotent terminal transitions, Elo calculation, and result persistence."""

from __future__ import annotations

from typing import Callable

from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_lifecycle_models import (
    LIVE_LIFECYCLE_STATE_VALUES,
    TERMINAL_LIFECYCLE_STATES,
    GameLifecycleState,
)
from .game_mode import GameMode, MatchOutcome, PlayerSeat


class GameResultFinalizer:
    _WINNER_SEATS = {
        MatchOutcome.FIRST_PLAYER_WIN: PlayerSeat.FIRST_PLAYER,
        MatchOutcome.SECOND_PLAYER_WIN: PlayerSeat.SECOND_PLAYER,
        MatchOutcome.DRAW: None,
    }
    _PERSISTED_OUTCOMES = {
        MatchOutcome.FIRST_PLAYER_WIN: "WHITE_WIN",
        MatchOutcome.SECOND_PLAYER_WIN: "BLACK_WIN",
        MatchOutcome.DRAW: "DRAW",
    }

    def __init__(
        self,
        lifecycle_repository,
        user_repository,
        match_repository,
        elo_service,
        token_service,
        view_factory,
        *,
        room_repository=None,
        pause_session=None,
        teardown_runtime=None,
        seat_adapter=CHESS_SEAT_ADAPTER,
    ):
        self._lifecycles = lifecycle_repository
        self._users = user_repository
        self._matches = match_repository
        self._elo = elo_service
        self._tokens = token_service
        self._views = view_factory
        self._rooms = room_repository
        self._pause_session = pause_session or (lambda _game_id: None)
        self._teardown_runtime = teardown_runtime or (lambda _game_id: None)
        self._seat_adapter = seat_adapter
        self.on_terminal: Callable[[str], None] | None = None

    def outcome_for_color(self, color: str) -> MatchOutcome:
        winner = self._seat_adapter.seat_for_color(color)
        return self.outcome_for_winner(winner)

    @staticmethod
    def outcome_for_winner(winner: PlayerSeat) -> MatchOutcome:
        return (
            MatchOutcome.FIRST_PLAYER_WIN
            if winner is PlayerSeat.FIRST_PLAYER
            else MatchOutcome.SECOND_PLAYER_WIN
        )

    def forfeit(self, record, forfeiting_player, *, now_ms: int):
        winner = next(
            player
            for player in self._lifecycles.players(record.game_id)
            if player.user_id != forfeiting_player.user_id
        )
        outcome = self.outcome_for_winner(PlayerSeat(winner.seat))
        return self.finalize(record, outcome, reason="forfeit", now_ms=now_ms)

    def finalize(
        self,
        record,
        outcome: MatchOutcome,
        *,
        reason: str,
        now_ms: int,
    ):
        if GameLifecycleState(record.state) in TERMINAL_LIFECYCLE_STATES:
            return self._views.create(record, changed=False)
        resolved_outcome = MatchOutcome(outcome)
        players = self._lifecycles.players(record.game_id)
        first = next(
            item for item in players if item.seat == PlayerSeat.FIRST_PLAYER.value
        )
        second = next(
            item for item in players if item.seat == PlayerSeat.SECOND_PLAYER.value
        )
        if record.ranked and record.mode == GameMode.PLAY.value:
            self._save_ranked_result(
                record,
                first,
                second,
                resolved_outcome,
                reason=reason,
                now_ms=now_ms,
            )
        return self.terminal(
            record,
            GameLifecycleState.ENDED,
            reason=reason,
            now_ms=now_ms,
            winner_seat=self._WINNER_SEATS[resolved_outcome],
        )

    def terminal(
        self,
        record,
        state: GameLifecycleState,
        *,
        reason: str,
        now_ms: int,
        winner_seat: PlayerSeat | None = None,
    ):
        if GameLifecycleState(record.state) in TERMINAL_LIFECYCLE_STATES:
            return self._views.create(record, changed=False)
        if not self._lifecycles.transition(
            record.game_id,
            from_states=LIVE_LIFECYCLE_STATE_VALUES,
            target=state.value,
            now_ms=now_ms,
            reason=reason,
            winner_seat=None if winner_seat is None else winner_seat.value,
        ):
            current = self._lifecycles.by_id(record.game_id)
            return self._views.create(current, changed=False)
        self.revoke_tokens(record.game_id, now_ms=now_ms)
        self._pause_session(record.game_id)
        self._teardown_runtime(record.game_id)
        self._update_room(record, state, reason=reason, now_ms=now_ms)
        if self.on_terminal is not None:
            self.on_terminal(record.game_id)
        return self._views.create(self._lifecycles.by_id(record.game_id))

    def revoke_tokens(self, game_id: str, *, now_ms: int) -> int:
        return self._tokens.revoke_game_tokens(game_id, now_ms=now_ms)

    def _save_ranked_result(
        self,
        record,
        first,
        second,
        outcome: MatchOutcome,
        *,
        reason: str,
        now_ms: int,
    ) -> None:
        first_user = self._users.by_id(first.user_id)
        second_user = self._users.by_id(second.user_id)
        ratings = self._elo.calculate(first_user.rating, second_user.rating, outcome)
        self._matches.save_ranked_result(
            game_id=record.game_id,
            white_user_id=first.user_id,
            black_user_id=second.user_id,
            outcome=self._PERSISTED_OUTCOMES[outcome],
            reason=reason,
            white_rating_before=ratings.first_player_rating_before,
            white_rating_after=ratings.first_player_rating_after,
            black_rating_before=ratings.second_player_rating_before,
            black_rating_after=ratings.second_player_rating_after,
            now_ms=now_ms,
        )

    def _update_room(
        self,
        record,
        state: GameLifecycleState,
        *,
        reason: str,
        now_ms: int,
    ) -> None:
        if self._rooms is None or record.room_id is None:
            return
        if state is GameLifecycleState.ENDED:
            self._rooms.end(record.room_id, reason=reason, now_ms=now_ms)
            return
        self._rooms.close(
            record.room_id,
            reason=reason,
            now_ms=now_ms,
            interrupted=state is GameLifecycleState.INTERRUPTED,
        )
