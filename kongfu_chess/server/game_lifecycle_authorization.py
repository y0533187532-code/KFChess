"""Authentication and player-seat authorization for lifecycle operations."""

from __future__ import annotations

from ..protocol import ProtocolErrorCode
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_lifecycle_models import GameLifecycleError
from .game_mode import GameRole, PlayerSeat


class GameLifecycleAuthorization:
    def __init__(self, auth_service, token_service, *, seat_adapter=CHESS_SEAT_ADAPTER):
        self._auth = auth_service
        self._tokens = token_service
        self._seat_adapter = seat_adapter

    def validate_auth_token(self, auth_token: str, *, now_ms: int):
        return self._auth.validate_auth_token(auth_token, now_ms=now_ms)

    def validate_game_token(
        self,
        game_token: str,
        *,
        game_id: str,
        user_id: int,
        lifecycle_player,
        now_ms: int,
    ):
        token = self._tokens.verify_game(
            game_token, game_id=game_id, now_ms=now_ms
        )
        self._authorize_token(user_id, lifecycle_player, token)
        return token

    def _authorize_token(self, user_id: int, lifecycle_player, token) -> None:
        if token is None:
            raise GameLifecycleError(ProtocolErrorCode.INVALID_TOKEN)
        if token.user_id != user_id or token.role != GameRole.PLAYER.value:
            raise GameLifecycleError(ProtocolErrorCode.FORBIDDEN)
        if token.color is None:
            raise GameLifecycleError(ProtocolErrorCode.FORBIDDEN)
        try:
            token_seat = self._seat_adapter.seat_for_color(token.color)
        except (TypeError, ValueError) as exc:
            raise GameLifecycleError(ProtocolErrorCode.FORBIDDEN) from exc
        if token_seat is not PlayerSeat(lifecycle_player.seat):
            raise GameLifecycleError(ProtocolErrorCode.FORBIDDEN)
