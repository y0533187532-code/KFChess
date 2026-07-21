"""Game-over, terminal transition, and restart-recovery workflow."""

from __future__ import annotations

from ..model import GameOverEvent
from .game_lifecycle_models import GameLifecycleState, GameLifecycleView
from .game_mode import MatchOutcome


class GameLifecycleTerminalWorkflow:
    def __init__(self, coordinator, finalizer, *, room_repository=None):
        self._context = coordinator
        self._finalizer = finalizer
        self._rooms = room_repository

    def consume_game_over(
        self, game_id: str, event: GameOverEvent
    ) -> GameLifecycleView:
        outcome = self._finalizer.outcome_for_color(event.winning_color)
        return self.finalize_result(
            game_id, outcome, reason="game_over", now_ms=event.ended_at_ms
        )

    def finalize_result(
        self,
        game_id: str,
        outcome: MatchOutcome,
        *,
        reason: str,
        now_ms: int,
    ) -> GameLifecycleView:
        with self._context.lock:
            return self._finalizer.finalize(
                self._context.require(game_id),
                MatchOutcome(outcome),
                reason=reason,
                now_ms=now_ms,
            )

    def interrupt(self, game_id: str, *, now_ms: int) -> GameLifecycleView:
        with self._context.lock:
            return self._finalizer.terminal(
                self._context.require(game_id),
                GameLifecycleState.INTERRUPTED,
                reason="interrupted",
                now_ms=now_ms,
            )

    def cancel(
        self, game_id: str, *, reason: str, now_ms: int
    ) -> GameLifecycleView:
        with self._context.lock:
            return self._finalizer.terminal(
                self._context.require(game_id),
                GameLifecycleState.CANCELLED,
                reason=reason,
                now_ms=now_ms,
            )

    def recover_after_restart(
        self, *, now_ms: int
    ) -> tuple[GameLifecycleView, ...]:
        with self._context.lock:
            recovered = self._context.lifecycles.recover_nonterminal(
                now_ms=now_ms
            )
            views = []
            for previous in recovered:
                self._finalizer.revoke_tokens(previous.game_id, now_ms=now_ms)
                self._context.pause_session(previous.game_id)
                if self._rooms is not None and previous.room_id is not None:
                    interrupted = previous.state in {
                        GameLifecycleState.ACTIVE.value,
                        GameLifecycleState.PAUSED_FOR_RECONNECT.value,
                    }
                    self._rooms.close(
                        previous.room_id,
                        reason="server_restart",
                        now_ms=now_ms,
                        interrupted=interrupted,
                    )
                views.append(
                    self._context.views.create(
                        self._context.require(previous.game_id)
                    )
                )
            return tuple(views)

    def subscriber_for(self, lifecycle_service, game_id: str):
        return GameOverLifecycleSubscriber(lifecycle_service, game_id)


class GameOverLifecycleSubscriber:
    """Bind engine GameOverEvent delivery to one authoritative game id."""

    def __init__(self, lifecycle_service, game_id: str):
        self._lifecycle_service = lifecycle_service
        self._game_id = game_id

    def handle(self, event: GameOverEvent) -> None:
        self._lifecycle_service.consume_game_over(self._game_id, event)
