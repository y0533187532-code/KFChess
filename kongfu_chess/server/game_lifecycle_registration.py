"""Registration and activation workflow for Play and Room games."""

from __future__ import annotations

import sqlite3

from ..protocol import ProtocolErrorCode
from .game_lifecycle_models import (
    GameLifecycleError,
    GameLifecycleState,
    GameLifecycleView,
)
from .game_mode import GameMode, PlayerSeat


class GameLifecycleRegistration:
    def __init__(
        self,
        coordinator,
        *,
        room_repository=None,
        runtime_factory=None,
        max_active_games: int | None = None,
    ):
        self._context = coordinator
        self._rooms = room_repository
        self._runtime_factory = runtime_factory
        self._max_active_games = max_active_games

    def _start_runtime(self, game_id: str) -> None:
        if self._runtime_factory is not None:
            self._runtime_factory.start(game_id)

    def register_play_match(self, match, *, now_ms: int | None = None):
        created_at_ms = match.created_at_ms if now_ms is None else now_ms
        players = tuple((seat.user_id, seat.seat) for seat in match.seats)
        view = self.register_game(
            match.game_id,
            GameMode.PLAY,
            players,
            ranked=match.ranked,
            initial_state=GameLifecycleState.ACTIVE,
            now_ms=created_at_ms,
        )
        self._start_runtime(match.game_id)
        return view

    def register_room(
        self,
        *,
        room_id: int,
        game_id: str,
        creator_user_id: int,
        now_ms: int,
    ):
        return self.register_game(
            game_id,
            GameMode.ROOM,
            ((creator_user_id, PlayerSeat.FIRST_PLAYER),),
            ranked=False,
            initial_state=GameLifecycleState.WAITING_TO_START,
            room_id=room_id,
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
        with self._context.lock:
            resolved_mode = GameMode(mode)
            if ranked and resolved_mode is not GameMode.PLAY:
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            existing = self._context.lifecycles.by_id(game_id)
            if existing is not None:
                return self._context.views.create(existing, changed=False)
            if (
                self._max_active_games is not None
                and self._context.lifecycles.count_live_games()
                >= self._max_active_games
            ):
                raise GameLifecycleError(ProtocolErrorCode.ACTIVE_GAMES_FULL)
            normalized_players = tuple(
                (user_id, PlayerSeat(seat).value) for user_id, seat in players
            )
            try:
                record = self._context.lifecycles.create(
                    game_id=game_id,
                    mode=resolved_mode.value,
                    ranked=ranked,
                    state=GameLifecycleState(initial_state).value,
                    players=normalized_players,
                    room_id=room_id,
                    now_ms=now_ms,
                )
            except sqlite3.IntegrityError as exc:
                raise GameLifecycleError(
                    ProtocolErrorCode.INVALID_GAME_STATE
                ) from exc
            return self._context.views.create(record)

    def mark_waiting_to_start(
        self, game_id: str, *, now_ms: int
    ) -> GameLifecycleView:
        with self._context.lock:
            if not self._context.lifecycles.transition(
                game_id,
                from_states=(GameLifecycleState.CREATED.value,),
                target=GameLifecycleState.WAITING_TO_START.value,
                now_ms=now_ms,
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            return self._context.views.create(self._context.require(game_id))

    def activate_game(self, game_id: str, *, now_ms: int) -> GameLifecycleView:
        with self._context.lock:
            self._context.require(game_id)
            if len(self._context.lifecycles.players(game_id)) != 2:
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            if not self._context.lifecycles.transition(
                game_id,
                from_states=(
                    GameLifecycleState.CREATED.value,
                    GameLifecycleState.WAITING_TO_START.value,
                ),
                target=GameLifecycleState.ACTIVE.value,
                now_ms=now_ms,
                double_disconnect=False,
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            view = self._context.views.create(self._context.require(game_id))
            self._start_runtime(game_id)
            return view

    def add_room_player(
        self, game_id: str, user_id: int, seat: PlayerSeat, *, now_ms: int
    ) -> GameLifecycleView:
        del now_ms
        with self._context.lock:
            record = self._context.require(game_id)
            if (
                record.mode != GameMode.ROOM.value
                or not self._context.lifecycles.add_player(
                    game_id, user_id, PlayerSeat(seat).value
                )
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            return self._context.views.create(self._context.require(game_id))

    def remove_room_player(self, game_id: str, user_id: int) -> GameLifecycleView:
        with self._context.lock:
            record = self._context.require(game_id)
            if (
                record.mode != GameMode.ROOM.value
                or not self._context.lifecycles.remove_player(game_id, user_id)
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            return self._context.views.create(self._context.require(game_id))

    def start_room_game(self, game_id: str, *, now_ms: int) -> GameLifecycleView:
        with self._context.lock:
            record = self._context.require(game_id)
            players = self._context.lifecycles.players(game_id)
            if (
                record.mode != GameMode.ROOM.value
                or record.state != GameLifecycleState.WAITING_TO_START.value
                or len(players) != 2
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            if self._rooms is not None and not self._rooms.mark_started(
                record.room_id, now_ms=now_ms
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            if not self._context.lifecycles.transition(
                game_id,
                from_states=(GameLifecycleState.WAITING_TO_START.value,),
                target=GameLifecycleState.ACTIVE.value,
                now_ms=now_ms,
                double_disconnect=False,
            ):
                raise GameLifecycleError(ProtocolErrorCode.INVALID_GAME_STATE)
            view = self._context.views.create(self._context.require(game_id))
            self._start_runtime(game_id)
            return view
