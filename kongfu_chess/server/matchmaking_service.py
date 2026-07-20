"""Authenticated in-memory matchmaking for ranked Play games."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable

from ..protocol import ProtocolErrorCode
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_mode import (
    PLAY_GAME_MODE,
    GameModeConfig,
    GameRole,
    PlayerSeat,
    SeatAssignmentPolicy,
    SeatBoundaryAdapter,
)


class MatchmakingError(ValueError):
    def __init__(self, code: ProtocolErrorCode):
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class QueueTicket:
    user_id: int
    username: str
    rating: int
    enqueued_at_ms: int
    expires_at_ms: int
    order: int


@dataclass(frozen=True)
class PlaySeat:
    user_id: int
    username: str
    rating: int
    seat: PlayerSeat
    game_token: str
    role: GameRole = GameRole.PLAYER


@dataclass(frozen=True)
class PlayMatchView:
    game_id: str
    user_id: int
    seat: PlayerSeat
    game_token: str
    opponent_user_id: int
    opponent_username: str
    opponent_rating: int
    ranked: bool
    mode: str


@dataclass(frozen=True)
class PlayMatch:
    game_id: str
    seats: tuple[PlaySeat, ...]
    created_at_ms: int
    game_mode: GameModeConfig = PLAY_GAME_MODE

    @property
    def ranked(self) -> bool:
        return self.game_mode.ranked

    @property
    def mode(self) -> str:
        return self.game_mode.mode.value

    def player_at(self, player_seat: PlayerSeat) -> PlaySeat:
        return next(seat for seat in self.seats if seat.seat is player_seat)

    @property
    def first_player(self) -> PlaySeat:
        return self.player_at(PlayerSeat.FIRST_PLAYER)

    @property
    def second_player(self) -> PlaySeat:
        return self.player_at(PlayerSeat.SECOND_PLAYER)

    def view_for(self, user_id: int) -> PlayMatchView:
        own = next((seat for seat in self.seats if seat.user_id == user_id), None)
        if own is None:
            raise ValueError("User is not a player in this match")
        opponents = tuple(seat for seat in self.seats if seat.user_id != user_id)
        if len(opponents) != 1:
            raise ValueError("The current Play match view requires one opponent")
        opponent = opponents[0]
        return PlayMatchView(
            game_id=self.game_id,
            user_id=own.user_id,
            seat=own.seat,
            game_token=own.game_token,
            opponent_user_id=opponent.user_id,
            opponent_username=opponent.username,
            opponent_rating=opponent.rating,
            ranked=self.ranked,
            mode=self.mode,
        )


@dataclass(frozen=True)
class MatchmakingStatus:
    state: str
    user_id: int
    ticket: QueueTicket | None = None
    match: PlayMatchView | None = None


class MatchmakingService:
    def __init__(
        self,
        auth_service,
        token_service,
        *,
        rating_range: int,
        timeout_seconds: int,
        max_queue_users: int,
        seat_selector: Callable[..., tuple[int, ...]] | None = None,
        seat_assignment_policy: SeatAssignmentPolicy | None = None,
        game_mode: GameModeConfig = PLAY_GAME_MODE,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
        game_id_factory: Callable[[], str] | None = None,
    ):
        self._auth_service = auth_service
        self._token_service = token_service
        self._rating_range = rating_range
        self._timeout_ms = timeout_seconds * 1000
        self._max_queue_users = max_queue_users
        if seat_selector is not None and seat_assignment_policy is not None:
            raise ValueError(
                "Provide seat_selector or seat_assignment_policy, not both"
            )
        if seat_assignment_policy is None and seat_selector is not None:
            seat_assignment_policy = SeatAssignmentPolicy(
                lambda players: seat_selector(*players)
            )
        self._seat_assignment_policy = (
            seat_assignment_policy or SeatAssignmentPolicy()
        )
        self._game_mode = game_mode
        self._seat_adapter = seat_adapter
        self._game_id_factory = game_id_factory or (lambda: uuid.uuid4().hex)
        self._tickets: dict[int, QueueTicket] = {}
        self._matches_by_user: dict[int, PlayMatch] = {}
        self._matches_by_id: dict[str, PlayMatch] = {}
        self._timed_out_users: set[int] = set()
        self._next_order = 0

    @classmethod
    def from_config(
        cls,
        auth_service,
        token_service,
        config,
        **overrides,
    ):
        return cls(
            auth_service,
            token_service,
            rating_range=config.elo.matchmaking_range,
            timeout_seconds=config.timing.matchmaking_timeout_seconds,
            max_queue_users=config.capacity.matchmaking_users,
            **overrides,
        )

    def join(self, auth_token: str, *, now_ms: int) -> MatchmakingStatus:
        principal = self._auth_service.validate_auth_token(auth_token, now_ms=now_ms)
        self.expire(now_ms=now_ms)
        user_id = principal.user_id
        self._timed_out_users.discard(user_id)
        if user_id in self._matches_by_user:
            raise MatchmakingError(ProtocolErrorCode.ALREADY_IN_GAME)
        if user_id in self._tickets:
            raise MatchmakingError(ProtocolErrorCode.ALREADY_IN_MATCHMAKING)

        candidate = self._oldest_compatible(principal.rating)
        if candidate is not None:
            self._tickets.pop(candidate.user_id)
            match = self._create_match(candidate, principal, now_ms=now_ms)
            return MatchmakingStatus(
                "MATCH_FOUND", user_id, match=match.view_for(user_id)
            )
        if len(self._tickets) >= self._max_queue_users:
            raise MatchmakingError(ProtocolErrorCode.MATCHMAKING_QUEUE_FULL)
        ticket = QueueTicket(
            user_id=user_id,
            username=principal.username,
            rating=principal.rating,
            enqueued_at_ms=now_ms,
            expires_at_ms=now_ms + self._timeout_ms,
            order=self._next_order,
        )
        self._next_order += 1
        self._tickets[user_id] = ticket
        return MatchmakingStatus("QUEUED", user_id, ticket=ticket)

    def cancel(self, auth_token: str, *, now_ms: int) -> MatchmakingStatus:
        principal = self._auth_service.validate_auth_token(auth_token, now_ms=now_ms)
        self.expire(now_ms=now_ms)
        if principal.user_id in self._matches_by_user:
            raise MatchmakingError(ProtocolErrorCode.ALREADY_IN_GAME)
        self._tickets.pop(principal.user_id, None)
        self._timed_out_users.discard(principal.user_id)
        return MatchmakingStatus("IDLE", principal.user_id)

    def status(self, auth_token: str, *, now_ms: int) -> MatchmakingStatus:
        principal = self._auth_service.validate_auth_token(auth_token, now_ms=now_ms)
        self.expire(now_ms=now_ms)
        user_id = principal.user_id
        match = self._matches_by_user.get(user_id)
        if match is not None:
            return MatchmakingStatus(
                "MATCH_FOUND", user_id, match=match.view_for(user_id)
            )
        ticket = self._tickets.get(user_id)
        if ticket is not None:
            return MatchmakingStatus("QUEUED", user_id, ticket=ticket)
        if user_id in self._timed_out_users:
            return MatchmakingStatus("TIMED_OUT", user_id)
        return MatchmakingStatus("IDLE", user_id)

    def disconnect_user(self, user_id: int) -> bool:
        removed = self._tickets.pop(user_id, None) is not None
        self._timed_out_users.discard(user_id)
        return removed

    def expire(self, *, now_ms: int) -> tuple[int, ...]:
        expired = tuple(
            ticket.user_id
            for ticket in sorted(self._tickets.values(), key=lambda item: item.order)
            if now_ms >= ticket.expires_at_ms
        )
        for user_id in expired:
            self._tickets.pop(user_id, None)
            self._timed_out_users.add(user_id)
        return expired

    @property
    def queued_user_ids(self) -> tuple[int, ...]:
        return tuple(
            ticket.user_id
            for ticket in sorted(self._tickets.values(), key=lambda item: item.order)
        )

    def match_by_id(self, game_id: str) -> PlayMatch | None:
        return self._matches_by_id.get(game_id)

    def _oldest_compatible(self, rating: int) -> QueueTicket | None:
        compatible = (
            ticket
            for ticket in self._tickets.values()
            if abs(ticket.rating - rating) <= self._rating_range
        )
        return min(
            compatible,
            key=lambda item: (item.enqueued_at_ms, item.order),
            default=None,
        )

    def _create_match(self, waiting: QueueTicket, joining, *, now_ms: int) -> PlayMatch:
        player_ids = (waiting.user_id, joining.user_id)
        assignments = self._seat_assignment_policy.assign(
            player_ids, self._game_mode
        )
        game_id = self._game_id_factory()
        players = {
            waiting.user_id: (waiting.username, waiting.rating),
            joining.user_id: (joining.username, joining.rating),
        }
        seats = []
        for assignment in assignments:
            user_id, seat = assignment.user_id, assignment.seat
            username, rating = players[user_id]
            issued = self._token_service.issue_game(
                game_id=game_id,
                user_id=user_id,
                role=GameRole.PLAYER.value,
                color=self._seat_adapter.persistence_color(GameRole.PLAYER, seat),
                now_ms=now_ms,
            )
            seats.append(PlaySeat(
                user_id, username, rating, seat, issued.value
            ))
        match = PlayMatch(game_id, tuple(seats), now_ms, self._game_mode)
        self._matches_by_id[game_id] = match
        for seat in match.seats:
            self._matches_by_user[seat.user_id] = match
        return match
