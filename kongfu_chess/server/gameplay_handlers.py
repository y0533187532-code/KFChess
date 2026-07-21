"""Protocol routing for structured move and in-place jump requests."""

from __future__ import annotations

from collections.abc import Mapping

from ..protocol import MessageType, ProtocolError, ProtocolErrorCode
from .auth_service import AuthError
from .game_session import SessionCommandType
from .gameplay_service import (
    BoardCoordinate,
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

    def __init__(self, gameplay_service, *, clock_ms):
        self._gameplay_service = gameplay_service
        self._clock_ms = clock_ms

    def register_routes(self, router) -> None:
        router.register(MessageType.MOVE_REQUEST.value, self.move)
        router.register(MessageType.JUMP_REQUEST.value, self.jump)

    async def move(self, context) -> OutgoingMessage:
        return await self._execute(
            SessionCommandType.MOVE,
            context.envelope.request_id,
            self._request(context),
        )

    async def jump(self, context) -> OutgoingMessage:
        return await self._execute(
            SessionCommandType.JUMP,
            context.envelope.request_id,
            self._request(context),
        )

    async def _execute(self, kind, request_id, request) -> OutgoingMessage:
        try:
            result = await self._gameplay_service.submit(
                kind,
                request_id,
                request,
                now_ms=self._clock_ms(),
            )
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
