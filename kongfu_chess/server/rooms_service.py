"""Authenticated persistent rooms with neutral player seats and spectators."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Callable, Mapping

from ..protocol import ProtocolErrorCode
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_mode import GameRole, SeatBoundaryAdapter
from .room_code_policy import RoomCodePolicy
from .room_models import RoomStatus, RoomsError, RoomView
from .room_seating_policy import RoomSeatingPolicy
from .room_view_factory import RoomViewFactory


class RoomsService:
    # Compatibility aliases; RoomCodePolicy owns these decisions.
    CODE_LENGTH = RoomCodePolicy.CODE_LENGTH
    CODE_ALPHABET = RoomCodePolicy.CODE_ALPHABET
    _CLOSED_STATUSES = frozenset(
        {RoomStatus.CLOSED, RoomStatus.INTERRUPTED, RoomStatus.ENDED}
    )

    def __init__(
        self,
        auth_service,
        token_service,
        room_repository,
        *,
        max_spectators: int,
        max_open_rooms: int,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
        code_factory: Callable[[], str] | None = None,
        code_policy: RoomCodePolicy | None = None,
        seating_policy: RoomSeatingPolicy | None = None,
        view_factory: RoomViewFactory | None = None,
        game_id_factory: Callable[[], str] | None = None,
        active_game_checker: Callable[[int], bool] | None = None,
        snapshot_provider: Callable[[str], Mapping | None] | None = None,
        lifecycle_service=None,
    ):
        self._auth_service = auth_service
        self._tokens = token_service
        self._rooms = room_repository
        self._max_spectators = max_spectators
        self._max_open_rooms = max_open_rooms
        self._seat_adapter = seat_adapter
        if code_factory is not None and code_policy is not None:
            raise ValueError("Provide code_factory or code_policy, not both")
        self._code_policy = code_policy or RoomCodePolicy(code_factory)
        self._seating_policy = seating_policy or RoomSeatingPolicy()
        self._views = view_factory or RoomViewFactory(
            room_repository,
            seat_adapter,
            snapshot_provider=snapshot_provider,
        )
        self._game_id_factory = game_id_factory or (lambda: uuid.uuid4().hex)
        self._active_game_checker = active_game_checker or (lambda _user_id: False)
        self._lifecycle_service = lifecycle_service

    @classmethod
    def from_config(
        cls,
        auth_service,
        token_service,
        room_repository,
        config,
        **overrides,
    ):
        return cls(
            auth_service,
            token_service,
            room_repository,
            max_spectators=config.capacity.spectators_per_room,
            max_open_rooms=config.capacity.open_rooms,
            **overrides,
        )

    def create(self, auth_token: str, *, now_ms: int) -> RoomView:
        principal = self._auth_service.validate_auth_token(auth_token, now_ms=now_ms)
        self._ensure_available(principal.user_id)
        if self._rooms.count_open() >= self._max_open_rooms:
            raise RoomsError(ProtocolErrorCode.ROOM_FULL)

        room = self._create_unique_room(principal.user_id, now_ms=now_ms)
        assignment = self._seating_policy.assign_creator()
        color = self._seat_adapter.persistence_color(
            assignment.role, assignment.seat
        )
        member = self._rooms.add_member(
            room_id=room.id,
            user_id=principal.user_id,
            role=assignment.role.value,
            color=color,
            now_ms=now_ms,
        )
        issued = self._tokens.issue_game(
            game_id=room.game_id,
            user_id=principal.user_id,
            role=member.role,
            color=member.color,
            now_ms=now_ms,
        )
        if self._lifecycle_service is not None:
            self._lifecycle_service.register_room(
                room_id=room.id,
                game_id=room.game_id,
                creator_user_id=principal.user_id,
                now_ms=now_ms,
            )
        return self._views.create(room, member, game_token=issued.value)

    def join(self, auth_token: str, code: str, *, now_ms: int) -> RoomView:
        principal = self._auth_service.validate_auth_token(auth_token, now_ms=now_ms)
        normalized = self._code_policy.normalize(code)
        room = self._require_room(normalized)
        self._ensure_joinable(room)
        existing = self._rooms.active_membership_for_user(principal.user_id)
        if existing is not None:
            raise RoomsError(ProtocolErrorCode.ALREADY_IN_ROOM)
        if self._active_game_checker(principal.user_id):
            raise RoomsError(ProtocolErrorCode.ALREADY_IN_GAME)

        members = self._rooms.active_members(room.id)
        occupied_seats = {
            self._seat_adapter.seat_for_color(member.color)
            for member in members
            if member.role == GameRole.PLAYER.value and member.color is not None
        }
        assignment = self._seating_policy.assign_joiner(
            occupied_seats,
            gameplay_started=room.started_at_ms is not None,
        )
        role = assignment.role
        color = self._seat_adapter.persistence_color(role, assignment.seat)
        if role is GameRole.PLAYER:
            member = self._rooms.add_member(
                room_id=room.id,
                user_id=principal.user_id,
                role=role.value,
                color=color,
                now_ms=now_ms,
            )
            if room.status == RoomStatus.WAITING.value:
                self._rooms.activate(room.id)
            room = self._rooms.by_id(room.id)
            if self._lifecycle_service is not None:
                self._lifecycle_service.add_room_player(
                    room.game_id,
                    principal.user_id,
                    assignment.seat,
                    now_ms=now_ms,
                )
        else:
            spectator_count = sum(
                member.role == GameRole.SPECTATOR.value for member in members
            )
            if spectator_count >= self._max_spectators:
                raise RoomsError(ProtocolErrorCode.ROOM_FULL)
            member = self._rooms.add_member(
                room_id=room.id,
                user_id=principal.user_id,
                role=role.value,
                color=color,
                now_ms=now_ms,
            )

        issued = self._tokens.issue_game(
            game_id=room.game_id,
            user_id=principal.user_id,
            role=role.value,
            color=color,
            now_ms=now_ms,
        )
        return self._views.create(room, member, game_token=issued.value)

    def status(self, auth_token: str, code: str, *, now_ms: int) -> RoomView:
        principal = self._auth_service.validate_auth_token(auth_token, now_ms=now_ms)
        room = self._require_room(self._code_policy.normalize(code))
        member = self._member_for(room.id, principal.user_id)
        return self._views.create(room, member)

    def leave(self, auth_token: str, code: str, *, now_ms: int) -> RoomView:
        principal = self._auth_service.validate_auth_token(auth_token, now_ms=now_ms)
        room = self._require_room(self._code_policy.normalize(code))
        member = self._member_for(room.id, principal.user_id)
        role = GameRole(member.role)
        seat = (
            None
            if member.color is None
            else self._seat_adapter.seat_for_color(member.color)
        )

        if role is GameRole.PLAYER and room.started_at_ms is not None:
            return self._views.create(room, member, leave_deferred=True)

        self._rooms.leave_member(member.id, now_ms=now_ms)
        self._tokens.revoke_user_game_tokens(
            room.game_id, principal.user_id, now_ms=now_ms
        )
        if role is GameRole.PLAYER and seat is self._seating_policy.creator_seat:
            self._rooms.close(room.id, reason="creator_left", now_ms=now_ms)
            self._tokens.revoke_game_tokens(room.game_id, now_ms=now_ms)
            if self._lifecycle_service is not None:
                self._lifecycle_service.cancel(
                    room.game_id, reason="creator_left", now_ms=now_ms
                )
        elif role is GameRole.PLAYER and seat is self._seating_policy.opponent_seat:
            self._rooms.return_to_waiting(room.id)
            if self._lifecycle_service is not None:
                self._lifecycle_service.remove_room_player(
                    room.game_id, principal.user_id
                )
        room = self._rooms.by_id(room.id)
        return self._views.create(room, member, departed=True)

    def mark_gameplay_started(self, room_id: int, *, now_ms: int) -> bool:
        return self._rooms.mark_started(room_id, now_ms=now_ms)

    def end(self, room_id: int, *, reason: str, now_ms: int) -> bool:
        ended = self._rooms.end(room_id, reason=reason, now_ms=now_ms)
        if ended:
            room = self._rooms.by_id(room_id)
            self._tokens.revoke_game_tokens(room.game_id, now_ms=now_ms)
        return ended

    def recover_after_restart(self, *, now_ms: int) -> tuple[int, int]:
        open_rooms = self._rooms.open_rooms()
        result = self._rooms.recover_open_rooms(now_ms=now_ms)
        for room in open_rooms:
            self._tokens.revoke_game_tokens(room.game_id, now_ms=now_ms)
        return result

    @classmethod
    def normalize_code(cls, code: str) -> str:
        return RoomCodePolicy.normalize(code)

    def _create_unique_room(self, user_id: int, *, now_ms: int):
        for _attempt in range(32):
            code = self._code_policy.generate()
            try:
                return self._rooms.create(
                    code=code,
                    game_id=self._game_id_factory(),
                    creator_user_id=user_id,
                    now_ms=now_ms,
                )
            except sqlite3.IntegrityError:
                continue
        raise RoomsError(ProtocolErrorCode.ROOM_FULL)

    def _ensure_available(self, user_id: int) -> None:
        if self._rooms.active_membership_for_user(user_id) is not None:
            raise RoomsError(ProtocolErrorCode.ALREADY_IN_ROOM)
        if self._active_game_checker(user_id):
            raise RoomsError(ProtocolErrorCode.ALREADY_IN_GAME)

    def _require_room(self, code: str):
        room = self._rooms.by_code(code)
        if room is None:
            raise RoomsError(ProtocolErrorCode.ROOM_NOT_FOUND)
        return room

    def _ensure_joinable(self, room) -> None:
        if RoomStatus(room.status) in self._CLOSED_STATUSES:
            raise RoomsError(ProtocolErrorCode.ROOM_CLOSED)

    def _member_for(self, room_id: int, user_id: int):
        member = next(
            (
                member
                for member in self._rooms.active_members(room_id)
                if member.user_id == user_id
            ),
            None,
        )
        if member is None:
            raise RoomsError(ProtocolErrorCode.UNAUTHORIZED)
        return member
