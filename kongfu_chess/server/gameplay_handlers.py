"""Protocol routing for structured move and in-place jump requests."""

from __future__ import annotations

from collections.abc import Mapping

from ..protocol import MessageType, ProtocolError, ProtocolErrorCode
from .auth_service import AuthError
from .game_session import SessionCommandType
from .gameplay_service import (
    BoardCoordinate,
    GameSnapshotRequest,
    GameplayError,
    GameplayRequest,
)
from .routing import OutgoingMessage


class GameplayHandlers:
    _FIELDS = {
        "auth_token",
        "game_token",
        "game_id",
        "piece_id",
        "expected_from",
        "target",
    }

    def __init__(self, gameplay_service, *, clock_ms, game_connections=None):
        self._gameplay_service = gameplay_service
        self._clock_ms = clock_ms
        self._game_connections = game_connections

    def register_routes(self, router) -> None:
        router.register(MessageType.MOVE_REQUEST.value, self.move)
        router.register(MessageType.JUMP_REQUEST.value, self.jump)
        router.register(MessageType.RESYNC_REQUEST.value, self.resync)

    async def move(self, context) -> OutgoingMessage:
        request = self._request(context)
        return await self._execute(
            context,
            SessionCommandType.MOVE,
            context.envelope.request_id,
            request,
        )

    async def jump(self, context) -> OutgoingMessage:
        request = self._request(context)
        return await self._execute(
            context,
            SessionCommandType.JUMP,
            context.envelope.request_id,
            request,
        )

    async def resync(self, context) -> OutgoingMessage:
        payload = context.envelope.payload
        expected_fields = {"auth_token", "game_token", "game_id"}
        if set(payload) != expected_fields:
            raise self._invalid_payload()
        request = GameSnapshotRequest(
            auth_token=self._non_empty_string(payload.get("auth_token")),
            game_token=self._non_empty_string(payload.get("game_token")),
            game_id=self._non_empty_string(payload.get("game_id")),
        )
        try:
            result = await self._gameplay_service.snapshot(
                context.envelope.request_id,
                request,
                now_ms=self._clock_ms(),
            )
            self._bind_connection(context.connection_id, request)
        except (AuthError, GameplayError) as exc:
            return OutgoingMessage(
                MessageType.COMMAND_RESULT.value,
                {"accepted": False, "code": exc.code.value},
            )
        return OutgoingMessage(MessageType.SNAPSHOT.value, dict(result.payload))

    async def _execute(
        self, context, kind, request_id, request
    ) -> OutgoingMessage:
        try:
            result = await self._gameplay_service.submit(
                kind,
                request_id,
                request,
                now_ms=self._clock_ms(),
            )
            if result.accepted:
                self._bind_connection(context.connection_id, request)
        except (AuthError, GameplayError) as exc:
            return OutgoingMessage(
                MessageType.COMMAND_RESULT.value,
                {"accepted": False, "code": exc.code.value},
            )
        return OutgoingMessage(
            MessageType.COMMAND_RESULT.value,
            {
                "accepted": result.accepted,
                "code": result.code,
                "sequence": result.sequence,
                **dict(result.payload),
            },
        )

    def _bind_connection(self, connection_id, request) -> None:
        if self._game_connections is None:
            return
        principal = self._gameplay_service._auth_service.validate_auth_token(
            request.auth_token,
            now_ms=self._clock_ms(),
        )
        self._game_connections.bind(
            connection_id,
            request.game_id,
            principal.user_id,
        )

    @classmethod
    def _request(cls, context) -> GameplayRequest:
        payload = context.envelope.payload
        if set(payload) != cls._FIELDS:
            raise cls._invalid_payload()
        auth_token = cls._non_empty_string(payload.get("auth_token"))
        game_token = cls._non_empty_string(payload.get("game_token"))
        game_id = cls._non_empty_string(payload.get("game_id"))
        piece_id = payload.get("piece_id")
        if isinstance(piece_id, bool) or not isinstance(piece_id, int) or piece_id < 0:
            raise cls._invalid_payload()
        return GameplayRequest(
            auth_token=auth_token,
            game_token=game_token,
            game_id=game_id,
            piece_id=piece_id,
            expected_from=cls._coordinate(payload.get("expected_from")),
            target=cls._coordinate(payload.get("target")),
        )

    @classmethod
    def _coordinate(cls, value) -> BoardCoordinate:
        if not isinstance(value, Mapping) or set(value) != {"row", "col"}:
            raise cls._invalid_payload()
        row, col = value.get("row"), value.get("col")
        if any(
            isinstance(item, bool) or not isinstance(item, int) or item < 0
            for item in (row, col)
        ):
            raise cls._invalid_payload()
        return BoardCoordinate(row, col)

    @classmethod
    def _non_empty_string(cls, value) -> str:
        if not isinstance(value, str) or not value:
            raise cls._invalid_payload()
        return value

    @staticmethod
    def _invalid_payload() -> ProtocolError:
        return ProtocolError(
            ProtocolErrorCode.INVALID_FIELD,
            "Gameplay payload does not match its schema",
        )
