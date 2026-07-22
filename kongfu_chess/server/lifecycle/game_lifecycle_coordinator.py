"""Shared lifecycle dependencies and helpers used by workflow modules."""

from __future__ import annotations

from ...protocol import ProtocolErrorCode
from .game_lifecycle_models import GameLifecycleError


class GameLifecycleCoordinator:
    """Keep cross-workflow helpers and synchronization in one place."""

    def __init__(
        self,
        lifecycle_repository,
        authorization,
        view_factory,
        lock,
        *,
        sessions=None,
    ):
        self.lifecycles = lifecycle_repository
        self.authorization = authorization
        self.views = view_factory
        self.lock = lock
        self._sessions = sessions

    def authenticate(
        self, auth_token: str, game_token: str, game_id: str, *, now_ms: int
    ):
        principal = self.authorization.validate_auth_token(
            auth_token, now_ms=now_ms
        )
        record = self.require(game_id)
        player = self.player_for(game_id, principal.user_id)
        self.authorization.validate_game_token(
            game_token,
            game_id=game_id,
            user_id=principal.user_id,
            lifecycle_player=player,
            now_ms=now_ms,
        )
        return principal, record, player

    def require(self, game_id: str):
        record = self.lifecycles.by_id(game_id)
        if record is None:
            raise GameLifecycleError(ProtocolErrorCode.GAME_NOT_FOUND)
        return record

    def player_for(self, game_id: str, user_id: int):
        player = next(
            (
                item
                for item in self.lifecycles.players(game_id)
                if item.user_id == user_id
            ),
            None,
        )
        if player is None:
            raise GameLifecycleError(ProtocolErrorCode.FORBIDDEN)
        return player

    def pause_session(self, game_id: str) -> None:
        if self._sessions is not None:
            self._sessions.pause(game_id)

    def resume_session(self, game_id: str) -> None:
        if self._sessions is not None:
            self._sessions.resume(game_id)
