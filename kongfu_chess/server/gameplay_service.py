"""Authenticated network commands translated to the existing engine API."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from ..engine.reasons import MoveReason
from ..engine.types import GameSnapshot
from ..protocol import ProtocolErrorCode, serialize_game_snapshot
from .tick_scheduler import needs_advancement
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_mode import GameRole, PlayerSeat, SeatBoundaryAdapter
from .game_session import (
    GameSession,
    HandlerResult,
    SessionCommand,
    SessionCommandType,
)


class GameplayError(ValueError):
    def __init__(self, code: ProtocolErrorCode):
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class BoardCoordinate:
    row: int
    col: int


@dataclass(frozen=True)
class GameplayRequest:
    auth_token: str
    game_token: str
    game_id: str
    piece_id: int
    expected_from: BoardCoordinate
    target: BoardCoordinate


@dataclass(frozen=True)
class GameSnapshotRequest:
    auth_token: str
    game_token: str
    game_id: str


class GameSessionRegistry:
    """In-memory lookup for live authoritative game queues."""

    def __init__(self):
        self._sessions: dict[str, GameSession] = {}

    def register(self, session: GameSession) -> None:
        if session.game_id in self._sessions:
            raise ValueError("A game session is already registered for this game")
        self._sessions[session.game_id] = session

    def get(self, game_id: str) -> GameSession | None:
        return self._sessions.get(game_id)

    def remove(self, game_id: str) -> GameSession | None:
        return self._sessions.pop(game_id, None)

    def game_ids(self) -> tuple[str, ...]:
        return tuple(self._sessions)

    def pause(self, game_id: str) -> bool:
        session = self.get(game_id)
        if session is None:
            return False
        session.pause()
        return True

    def resume(self, game_id: str) -> bool:
        session = self.get(game_id)
        if session is None:
            return False
        session.resume()
        return True


class GameplayCommandService:
    """Authenticate a request, authorize its game seat, then enqueue it."""

    def __init__(
        self,
        auth_service,
        token_service,
        sessions: GameSessionRegistry,
        *,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
        lifecycle_service=None,
    ):
        self._auth_service = auth_service
        self._token_service = token_service
        self._sessions = sessions
        self._seat_adapter = seat_adapter
        self._lifecycle_service = lifecycle_service

    async def submit(
        self,
        kind: SessionCommandType,
        request_id: str,
        request: GameplayRequest,
        *,
        now_ms: int,
    ):
        if kind not in (SessionCommandType.MOVE, SessionCommandType.JUMP):
            raise GameplayError(ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE)
        principal = self._auth_service.validate_auth_token(
            request.auth_token, now_ms=now_ms
        )
        game_token = self._token_service.verify_game(
            request.game_token,
            game_id=request.game_id,
            now_ms=now_ms,
        )
        if game_token is None:
            raise GameplayError(ProtocolErrorCode.INVALID_TOKEN)
        if (
            game_token.user_id != principal.user_id
            or game_token.role != GameRole.PLAYER.value
            or game_token.color is None
        ):
            raise GameplayError(ProtocolErrorCode.FORBIDDEN)
        try:
            seat = self._seat_adapter.seat_for_color(game_token.color)
        except (TypeError, ValueError) as exc:
            raise GameplayError(ProtocolErrorCode.FORBIDDEN) from exc

        session = self._sessions.get(request.game_id)
        if session is None:
            raise GameplayError(ProtocolErrorCode.GAME_NOT_FOUND)
        result = await session.submit(
            SessionCommand(
                kind=kind.value,
                request_id=request_id,
                payload=MappingProxyType(
                    {
                        "seat": seat,
                        "piece_id": request.piece_id,
                        "expected_from": request.expected_from,
                        "target": request.target,
                    }
                ),
            )
        )
        if result.accepted and self._lifecycle_service is not None:
            self._lifecycle_service.record_accepted_command(
                request.game_id, principal.user_id
            )
        return result

    async def snapshot(
        self,
        request_id: str,
        request: GameSnapshotRequest,
        *,
        now_ms: int,
    ):
        """Authorize and serialize an authoritative snapshot in FIFO order."""

        principal = self._auth_service.validate_auth_token(
            request.auth_token, now_ms=now_ms
        )
        game_token = self._token_service.verify_game(
            request.game_token,
            game_id=request.game_id,
            now_ms=now_ms,
        )
        if game_token is None:
            raise GameplayError(ProtocolErrorCode.INVALID_TOKEN)
        if (
            game_token.user_id != principal.user_id
            or game_token.role
            not in {GameRole.PLAYER.value, GameRole.SPECTATOR.value}
        ):
            raise GameplayError(ProtocolErrorCode.FORBIDDEN)
        session = self._sessions.get(request.game_id)
        if session is None:
            raise GameplayError(ProtocolErrorCode.GAME_NOT_FOUND)
        return await session.submit(
            SessionCommand(
                kind=SessionCommandType.SNAPSHOT.value,
                request_id=request_id,
            )
        )


class NetworkGameAdapter:
    """Inspect authoritative snapshots and invoke coordinate-based engine calls."""

    _REASON_CODES = MappingProxyType(
        {
            MoveReason.OK: "ok",
            MoveReason.GAME_OVER: ProtocolErrorCode.GAME_OVER.value,
            MoveReason.PIECE_IN_MOTION: ProtocolErrorCode.PIECE_BUSY.value,
            MoveReason.PIECE_RESTING: ProtocolErrorCode.PIECE_BUSY.value,
            MoveReason.OUTSIDE_BOARD: ProtocolErrorCode.OUTSIDE_BOARD.value,
            MoveReason.EMPTY_SOURCE: ProtocolErrorCode.EMPTY_SOURCE.value,
            MoveReason.FRIENDLY_DESTINATION: ProtocolErrorCode.FRIENDLY_DESTINATION.value,
            MoveReason.ILLEGAL_PIECE_MOVE: ProtocolErrorCode.ILLEGAL_PIECE_MOVE.value,
            MoveReason.PATH_BLOCKED: ProtocolErrorCode.PATH_BLOCKED.value,
            MoveReason.DESTINATION_RESERVED: ProtocolErrorCode.DESTINATION_RESERVED.value,
        }
    )

    def __init__(
        self,
        engine,
        *,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
        tick_interval_ms: int = 50,
        clock_ms=None,
    ):
        self._engine = engine
        self._seat_adapter = seat_adapter
        self._tick_interval_ms = tick_interval_ms
        self._clock_ms = clock_ms or (lambda: 0)
        self._last_sync_wall_ms = self._clock_ms()

    @property
    def handlers(self):
        return MappingProxyType(
            {
                SessionCommandType.MOVE.value: self.handle_move,
                SessionCommandType.JUMP.value: self.handle_jump,
                SessionCommandType.SNAPSHOT.value: self.handle_snapshot,
                SessionCommandType.TICK.value: self.handle_tick,
            }
        )

    def handle_snapshot(self, _command: SessionCommand) -> HandlerResult:
        return HandlerResult(
            accepted=True,
            changed=False,
            code="ok",
            payload=serialize_game_snapshot(self._engine.snapshot()),
        )

    def handle_move(self, command: SessionCommand) -> HandlerResult:
        return self._handle(command, jump=False)

    def handle_jump(self, command: SessionCommand) -> HandlerResult:
        return self._handle(command, jump=True)

    def handle_tick(self, command: SessionCommand) -> HandlerResult:
        if not needs_advancement(self._engine):
            return HandlerResult(
                accepted=True,
                changed=False,
                code="ok",
            )
        interval_ms = command.payload.get("interval_ms", self._tick_interval_ms)
        before = self._engine.snapshot()
        self._engine.wait(interval_ms)
        self._last_sync_wall_ms = self._clock_ms()
        after = self._engine.snapshot()
        changed = _snapshot_changed(before, after)
        payload = {}
        if changed:
            payload["snapshot"] = serialize_game_snapshot(after)
        return HandlerResult(
            accepted=True,
            changed=changed,
            code="ok",
            payload=payload,
        )

    def _sync_elapsed_time(self) -> None:
        now_ms = self._clock_ms()
        elapsed = max(0, now_ms - self._last_sync_wall_ms)
        if elapsed > 0:
            self._engine.wait(elapsed)
        self._last_sync_wall_ms = now_ms

    def _handle(self, command: SessionCommand, *, jump: bool) -> HandlerResult:
        self._sync_elapsed_time()
        seat: PlayerSeat = command.payload["seat"]
        piece_id: int = command.payload["piece_id"]
        expected_from: BoardCoordinate = command.payload["expected_from"]
        target: BoardCoordinate = command.payload["target"]

        if jump and target != expected_from:
            return self._rejected(ProtocolErrorCode.INVALID_FIELD)

        snapshot = self._engine.snapshot()
        if snapshot.game_over:
            return self._rejected(ProtocolErrorCode.GAME_OVER)
        piece = next(
            (item for item in snapshot.pieces if item.piece_id == piece_id),
            None,
        )
        if piece is None:
            return self._rejected(ProtocolErrorCode.INVALID_PIECE)
        if piece.token[:1] != self._seat_adapter.protocol_color(seat):
            return self._rejected(ProtocolErrorCode.FORBIDDEN_PIECE)
        if (piece.row, piece.col) != (expected_from.row, expected_from.col):
            return HandlerResult(
                accepted=False,
                changed=False,
                code=ProtocolErrorCode.STALE_CLIENT_STATE.value,
                payload={
                    "piece_id": piece_id,
                    "actual_from": {"row": piece.row, "col": piece.col},
                },
            )

        if jump:
            result = self._engine.request_jump(expected_from.row, expected_from.col)
        else:
            result = self._engine.request_move(
                expected_from.row,
                expected_from.col,
                target.row,
                target.col,
            )
        code = self._REASON_CODES.get(
            result.reason, ProtocolErrorCode.INVALID_FIELD.value
        )
        payload = {"piece_id": piece_id}
        if result.is_accepted:
            payload["snapshot"] = serialize_game_snapshot(self._engine.snapshot())
        return HandlerResult(
            accepted=result.is_accepted,
            changed=result.is_accepted,
            code=code,
            payload=payload,
        )

    @staticmethod
    def _rejected(code: ProtocolErrorCode) -> HandlerResult:
        return HandlerResult(False, False, code.value)


def _snapshot_changed(before: GameSnapshot, after: GameSnapshot) -> bool:
    if before.game_over != after.game_over:
        return True
    if dict(before.score_by_color) != dict(after.score_by_color):
        return True
    if len(before.pieces) != len(after.pieces):
        return True
    before_pieces = tuple(
        (piece.piece_id, piece.row, piece.col, piece.state, piece.rest_remaining_ms)
        for piece in before.pieces
    )
    after_pieces = tuple(
        (piece.piece_id, piece.row, piece.col, piece.state, piece.rest_remaining_ms)
        for piece in after.pieces
    )
    if before_pieces != after_pieces:
        return True
    return before.active_motions != after.active_motions


def build_game_session(
    game_id: str,
    engine,
    *,
    initial_sequence: int,
    request_cache_size: int,
    seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
    tick_interval_ms: int = 50,
    clock_ms=None,
    on_sequence_changed=None,
) -> GameSession:
    adapter = NetworkGameAdapter(
        engine,
        seat_adapter=seat_adapter,
        tick_interval_ms=tick_interval_ms,
        clock_ms=clock_ms,
    )
    return GameSession(
        game_id,
        adapter.handlers,
        initial_sequence=initial_sequence,
        request_cache_size=request_cache_size,
        on_sequence_changed=on_sequence_changed,
    )
