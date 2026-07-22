"""Public facade for authoritative Play and Room game lifecycles."""

from __future__ import annotations

from threading import RLock

from ...model import GameOverEvent
from ..core.chess_compatibility import CHESS_SEAT_ADAPTER
from ..core.game_mode import GameMode, MatchOutcome, PlayerSeat
from ..gameplay.gameplay_service import GameSessionRegistry
from .game_lifecycle_authorization import GameLifecycleAuthorization
from .game_lifecycle_coordinator import GameLifecycleCoordinator
from .game_lifecycle_models import (
    LIVE_LIFECYCLE_STATE_VALUES,
    TERMINAL_LIFECYCLE_STATES,
    GameLifecycleError,
    GameLifecycleState,
    GameLifecycleView,
    LifecyclePlayer,
)
from .game_lifecycle_reconnect_workflow import (
    GameLifecycleReconnectWorkflow,
)
from .game_lifecycle_registration import GameLifecycleRegistration
from .game_lifecycle_terminal_workflow import (
    GameLifecycleTerminalWorkflow,
    GameOverLifecycleSubscriber,
)
from .game_lifecycle_view_factory import GameLifecycleViewFactory
from .game_result_finalizer import GameResultFinalizer
from .reconnect_policy import ReconnectAction, ReconnectPolicy


class GameLifecycleService:
    """Stable lifecycle API delegating each workflow to a focused collaborator."""

    # Compatibility aliases retained for callers that inspected the service class.
    _TERMINAL_STATES = TERMINAL_LIFECYCLE_STATES
    _LIVE_STATES = LIVE_LIFECYCLE_STATE_VALUES

    def __init__(
        self,
        auth_service,
        token_service,
        lifecycle_repository,
        user_repository,
        match_repository,
        elo_service,
        *,
        reconnect_grace_seconds: int,
        sessions=None,
        room_repository=None,
        seat_adapter=CHESS_SEAT_ADAPTER,
        runtime_factory=None,
        max_active_games: int | None = None,
    ):
        self._tokens = token_service
        self._lifecycles = lifecycle_repository
        self._runtime_factory = runtime_factory
        session_backend = (
            runtime_factory.registry if runtime_factory is not None else sessions
        )
        self._sessions = session_backend
        self._rooms = room_repository
        self._authorization = GameLifecycleAuthorization(
            auth_service, token_service, seat_adapter=seat_adapter
        )
        self._reconnect = ReconnectPolicy(
            grace_seconds=reconnect_grace_seconds
        )
        self._views = GameLifecycleViewFactory(lifecycle_repository)
        self._lock = RLock()
        self._context = GameLifecycleCoordinator(
            lifecycle_repository,
            self._authorization,
            self._views,
            self._lock,
            sessions=session_backend,
        )
        self._finalizer = GameResultFinalizer(
            lifecycle_repository,
            user_repository,
            match_repository,
            elo_service,
            token_service,
            self._views,
            room_repository=room_repository,
            pause_session=self._context.pause_session,
            teardown_runtime=(
                runtime_factory.teardown if runtime_factory is not None else None
            ),
            seat_adapter=seat_adapter,
        )
        self._registration = GameLifecycleRegistration(
            self._context,
            room_repository=room_repository,
            runtime_factory=runtime_factory,
            max_active_games=max_active_games,
        )
        self._reconnect_workflow = GameLifecycleReconnectWorkflow(
            self._context, token_service, self._reconnect, self._finalizer
        )
        self._terminal_workflow = GameLifecycleTerminalWorkflow(
            self._context, self._finalizer, room_repository=room_repository
        )

    @classmethod
    def from_config(
        cls,
        auth_service,
        token_service,
        lifecycle_repository,
        user_repository,
        match_repository,
        elo_service,
        config,
        **overrides,
    ):
        return cls(
            auth_service,
            token_service,
            lifecycle_repository,
            user_repository,
            match_repository,
            elo_service,
            reconnect_grace_seconds=config.timing.reconnect_grace_seconds,
            max_active_games=config.capacity.active_games,
            **overrides,
        )

    @classmethod
    def with_runtime(
        cls,
        auth_service,
        token_service,
        lifecycle_repository,
        user_repository,
        match_repository,
        elo_service,
        config,
        **overrides,
    ):
        from ..gameplay.game_runtime_factory import GameRuntimeFactory
        from ..gameplay.tick_scheduler import TickScheduler

        registry = GameSessionRegistry()
        scheduler = TickScheduler(tick_interval_ms=config.timing.tick_interval_ms)
        runtime_factory = GameRuntimeFactory(
            registry,
            scheduler,
            initial_sequence=config.network.initial_sequence,
            request_cache_size=config.network.request_cache_size,
        )
        service = cls(
            auth_service,
            token_service,
            lifecycle_repository,
            user_repository,
            match_repository,
            elo_service,
            reconnect_grace_seconds=config.timing.reconnect_grace_seconds,
            runtime_factory=runtime_factory,
            **overrides,
        )
        runtime_factory.bind_lifecycle(service)
        return service, registry, runtime_factory

    def register_play_match(self, match, *, now_ms: int | None = None):
        return self._registration.register_play_match(match, now_ms=now_ms)

    def register_room(
        self,
        *,
        room_id: int,
        game_id: str,
        creator_user_id: int,
        now_ms: int,
    ):
        return self._registration.register_room(
            room_id=room_id,
            game_id=game_id,
            creator_user_id=creator_user_id,
            now_ms=now_ms,
        )

    def register_game(
        self,
        game_id: str,
        mode: GameMode,
        players,
        *,
        ranked: bool,
        initial_state: GameLifecycleState = GameLifecycleState.CREATED,
        room_id: int | None = None,
        now_ms: int,
    ) -> GameLifecycleView:
        return self._registration.register_game(
            game_id,
            mode,
            players,
            ranked=ranked,
            initial_state=initial_state,
            room_id=room_id,
            now_ms=now_ms,
        )

    def mark_waiting_to_start(
        self, game_id: str, *, now_ms: int
    ) -> GameLifecycleView:
        return self._registration.mark_waiting_to_start(game_id, now_ms=now_ms)

    def activate_game(self, game_id: str, *, now_ms: int) -> GameLifecycleView:
        return self._registration.activate_game(game_id, now_ms=now_ms)

    def add_room_player(
        self, game_id: str, user_id: int, seat: PlayerSeat, *, now_ms: int
    ) -> GameLifecycleView:
        return self._registration.add_room_player(
            game_id, user_id, seat, now_ms=now_ms
        )

    def remove_room_player(self, game_id: str, user_id: int) -> GameLifecycleView:
        return self._registration.remove_room_player(game_id, user_id)

    def start_room_game(self, game_id: str, *, now_ms: int) -> GameLifecycleView:
        return self._registration.start_room_game(game_id, now_ms=now_ms)

    def disconnect(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        return self._reconnect_workflow.disconnect(
            auth_token, game_token, game_id, now_ms=now_ms
        )

    def resign(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        return self._reconnect_workflow.resign(
            auth_token, game_token, game_id, now_ms=now_ms
        )

    def set_terminal_listener(self, callback) -> None:
        self._finalizer.on_terminal = callback

    def disconnect_transport(
        self, game_id: str, user_id: int, *, now_ms: int
    ) -> GameLifecycleView | None:
        return self._reconnect_workflow.disconnect_transport(
            game_id, user_id, now_ms=now_ms
        )

    def reconnect(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        return self._reconnect_workflow.reconnect(
            auth_token, game_token, game_id, now_ms=now_ms
        )

    def status(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        return self._reconnect_workflow.status(
            auth_token, game_token, game_id, now_ms=now_ms
        )

    def record_accepted_command(self, game_id: str, user_id: int) -> bool:
        return self._reconnect_workflow.record_accepted_command(game_id, user_id)

    def user_in_active_game(self, user_id: int) -> bool:
        return self._lifecycles.user_in_live_game(user_id)

    def expire(
        self, *, now_ms: int, game_id: str | None = None
    ) -> tuple[GameLifecycleView, ...]:
        return self._reconnect_workflow.expire(now_ms=now_ms, game_id=game_id)

    def consume_game_over(
        self, game_id: str, event: GameOverEvent
    ) -> GameLifecycleView:
        return self._terminal_workflow.consume_game_over(game_id, event)

    def finalize_result(
        self,
        game_id: str,
        outcome: MatchOutcome,
        *,
        reason: str,
        now_ms: int,
    ) -> GameLifecycleView:
        return self._terminal_workflow.finalize_result(
            game_id, outcome, reason=reason, now_ms=now_ms
        )

    def interrupt(self, game_id: str, *, now_ms: int) -> GameLifecycleView:
        return self._terminal_workflow.interrupt(game_id, now_ms=now_ms)

    def cancel(
        self, game_id: str, *, reason: str, now_ms: int
    ) -> GameLifecycleView:
        return self._terminal_workflow.cancel(
            game_id, reason=reason, now_ms=now_ms
        )

    def recover_after_restart(
        self, *, now_ms: int
    ) -> tuple[GameLifecycleView, ...]:
        return self._terminal_workflow.recover_after_restart(now_ms=now_ms)

    def subscriber_for(self, game_id: str):
        return self._terminal_workflow.subscriber_for(self, game_id)

    # Private compatibility shims retained while callers migrate to workflows.
    def _authenticate(
        self, auth_token: str, game_token: str, game_id: str, *, now_ms: int
    ):
        return self._context.authenticate(
            auth_token, game_token, game_id, now_ms=now_ms
        )

    def _require(self, game_id: str):
        return self._context.require(game_id)

    def _player_for(self, game_id: str, user_id: int):
        return self._context.player_for(game_id, user_id)

    def _pause_session(self, game_id: str) -> None:
        self._context.pause_session(game_id)

    def _resume_session(self, game_id: str) -> None:
        self._context.resume_session(game_id)
