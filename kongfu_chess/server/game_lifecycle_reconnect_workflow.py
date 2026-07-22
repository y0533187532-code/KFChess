"""Disconnect, reconnect, status, and reconnect-expiry workflow."""

from __future__ import annotations

from ..protocol import ProtocolErrorCode
from .game_lifecycle_models import (
    GameLifecycleError,
    GameLifecycleState,
    GameLifecycleView,
)
from .reconnect_policy import ReconnectAction


class GameLifecycleReconnectWorkflow:
    def __init__(self, coordinator, token_service, reconnect_policy, finalizer):
        self._context = coordinator
        self._tokens = token_service
        self._reconnect = reconnect_policy
        self._finalizer = finalizer

    def disconnect(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        with self._context.lock:
            principal, record, player = self._context.authenticate(
                auth_token, game_token, game_id, now_ms=now_ms
            )
            if record.state not in {
                GameLifecycleState.ACTIVE.value,
                GameLifecycleState.PAUSED_FOR_RECONNECT.value,
            } or not player.connected:
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            deadline = self._reconnect.deadline(now_ms)
            if not self._tokens.begin_game_grace(
                game_token, grace_expires_at_ms=deadline
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_TOKEN)
            if not self._context.lifecycles.disconnect_player(
                game_id, principal.user_id, deadline_ms=deadline
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            players = self._context.lifecycles.players(game_id)
            double_disconnect = self._reconnect.is_double_disconnect(players)
            self._context.lifecycles.transition(
                game_id,
                from_states=(
                    GameLifecycleState.ACTIVE.value,
                    GameLifecycleState.PAUSED_FOR_RECONNECT.value,
                ),
                target=GameLifecycleState.PAUSED_FOR_RECONNECT.value,
                now_ms=now_ms,
                double_disconnect=record.double_disconnect or double_disconnect,
            )
            self._context.pause_session(game_id)
            return self._context.views.create(self._context.require(game_id))

    def resign(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        with self._context.lock:
            principal, record, player = self._context.authenticate(
                auth_token, game_token, game_id, now_ms=now_ms
            )
            if record.state not in {
                GameLifecycleState.ACTIVE.value,
                GameLifecycleState.PAUSED_FOR_RECONNECT.value,
            }:
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            return self._finalizer.forfeit(record, player, now_ms=now_ms)

    def disconnect_transport(
        self, game_id: str, user_id: int, *, now_ms: int
    ) -> GameLifecycleView | None:
        with self._context.lock:
            record = self._context.lifecycles.by_id(game_id)
            if record is None:
                return None
            try:
                player = self._context.player_for(game_id, user_id)
            except GameLifecycleError:
                return None
            if record.state not in {
                GameLifecycleState.ACTIVE.value,
                GameLifecycleState.PAUSED_FOR_RECONNECT.value,
            } or not player.connected:
                return None
            deadline = self._reconnect.deadline(now_ms)
            if not self._tokens.begin_game_grace_for_user(
                game_id, user_id, grace_expires_at_ms=deadline
            ):
                return None
            if not self._context.lifecycles.disconnect_player(
                game_id, user_id, deadline_ms=deadline
            ):
                return None
            players = self._context.lifecycles.players(game_id)
            double_disconnect = self._reconnect.is_double_disconnect(players)
            self._context.lifecycles.transition(
                game_id,
                from_states=(
                    GameLifecycleState.ACTIVE.value,
                    GameLifecycleState.PAUSED_FOR_RECONNECT.value,
                ),
                target=GameLifecycleState.PAUSED_FOR_RECONNECT.value,
                now_ms=now_ms,
                double_disconnect=record.double_disconnect or double_disconnect,
            )
            self._context.pause_session(game_id)
            return self._context.views.create(self._context.require(game_id))

    def reconnect(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        with self._context.lock:
            principal = self._context.authorization.validate_auth_token(
                auth_token, now_ms=now_ms
            )
            record = self._context.require(game_id)
            player = self._context.player_for(game_id, principal.user_id)
            if (
                record.state != GameLifecycleState.PAUSED_FOR_RECONNECT.value
                or player.connected
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            if self._reconnect.reconnect_has_expired(player, now_ms=now_ms):
                raise GameLifecycleError(ProtocolErrorCode.RECONNECT_EXPIRED)
            self._context.authorization.validate_game_token(
                game_token,
                game_id=game_id,
                user_id=principal.user_id,
                lifecycle_player=player,
                now_ms=now_ms,
            )
            if not self._tokens.restore_game(game_token, now_ms=now_ms):
                raise GameLifecycleError(ProtocolErrorCode.RECONNECT_EXPIRED)
            self._context.lifecycles.reconnect_player(game_id, principal.user_id)
            players = self._context.lifecycles.players(game_id)
            if self._reconnect.should_resume(players):
                self._context.lifecycles.transition(
                    game_id,
                    from_states=(
                        GameLifecycleState.PAUSED_FOR_RECONNECT.value,
                    ),
                    target=GameLifecycleState.ACTIVE.value,
                    now_ms=now_ms,
                    double_disconnect=False,
                )
                self._context.resume_session(game_id)
            return self._context.views.create(self._context.require(game_id))

    def status(
        self,
        auth_token: str,
        game_token: str,
        game_id: str,
        *,
        now_ms: int,
    ) -> GameLifecycleView:
        with self._context.lock:
            self._context.authenticate(
                auth_token, game_token, game_id, now_ms=now_ms
            )
            self.expire(now_ms=now_ms, game_id=game_id)
            return self._context.views.create(
                self._context.require(game_id), changed=False
            )

    def record_accepted_command(self, game_id: str, user_id: int) -> bool:
        with self._context.lock:
            return self._context.lifecycles.mark_meaningful_activity(
                game_id, user_id
            )

    def expire(
        self, *, now_ms: int, game_id: str | None = None
    ) -> tuple[GameLifecycleView, ...]:
        with self._context.lock:
            records = (
                (self._context.require(game_id),)
                if game_id is not None
                else self._context.lifecycles.paused()
            )
            changed = []
            for record in records:
                players = self._context.lifecycles.players(record.game_id)
                decision = self._reconnect.expiry_decision(
                    record, players, now_ms=now_ms
                )
                if decision.action is ReconnectAction.CANCEL:
                    changed.append(
                        self._finalizer.terminal(
                            record,
                            GameLifecycleState.CANCELLED,
                            reason=decision.reason,
                            now_ms=now_ms,
                        )
                    )
                elif decision.action is ReconnectAction.FORFEIT:
                    changed.append(
                        self._finalizer.forfeit(
                            record,
                            decision.forfeiting_player,
                            now_ms=now_ms,
                        )
                    )
            return tuple(changed)
