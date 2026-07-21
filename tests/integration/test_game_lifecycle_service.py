import asyncio

import pytest

from kongfu_chess.model import GameOverEvent
from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameLifecycleRepository,
    GameTokenRepository,
    MatchRepository,
    RoomRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from kongfu_chess.protocol import (
    EnvelopePolicy,
    MessageEnvelope,
    ProtocolError,
    ProtocolErrorCode,
)
from kongfu_chess.server import (
    AuthService,
    EloService,
    GameLifecycleError,
    GameLifecycleHandlers,
    GameLifecycleService,
    GameLifecycleState,
    GameMode,
    GameRole,
    MatchmakingService,
    MessageRouter,
    PasswordHasher,
    PlayerSeat,
    RequestContext,
    RoomsService,
)


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


class SessionControls:
    def __init__(self):
        self.paused = set()

    def pause(self, game_id):
        self.paused.add(game_id)
        return True

    def resume(self, game_id):
        self.paused.discard(game_id)
        return True


def system(tmp_path):
    database = SqliteDatabase(tmp_path / "lifecycle.sqlite3", busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    tokens = TokenService(
        AuthSessionRepository(database), GameTokenRepository(database), token_bytes=32
    )
    auth = AuthService(
        users,
        tokens,
        PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32),
        password_min_length=6,
        initial_rating=1200,
        auth_token_ttl_seconds=600,
    )
    controls = SessionControls()
    lifecycle_repo = GameLifecycleRepository(database)
    rooms_repo = RoomRepository(database)
    lifecycle = GameLifecycleService(
        auth,
        tokens,
        lifecycle_repo,
        users,
        MatchRepository(database),
        EloService(scale=400, k_factor=32, rating_floor=100),
        reconnect_grace_seconds=20,
        sessions=controls,
        room_repository=rooms_repo,
    )
    return database, users, tokens, auth, lifecycle_repo, rooms_repo, lifecycle, controls


def player(auth, username, *, now_ms=1000):
    account = auth.register(
        username=username,
        password="secret7",
        email=f"{username}@example.test",
        phone="0501234567",
        now_ms=now_ms,
    )
    session = auth.login(username=username, password="secret7", now_ms=now_ms + 1)
    return account.user_id, session.auth_token


def active_game(system_values, *, game_id="game-1", mode=GameMode.PLAY, ranked=True):
    _, _, tokens, auth, _, _, lifecycle, _ = system_values
    first_id, first_auth = player(auth, "First")
    second_id, second_auth = player(auth, "Second", now_ms=1100)
    first_game = tokens.issue_game(
        game_id=game_id,
        user_id=first_id,
        role=GameRole.PLAYER.value,
        color="w",
        now_ms=2000,
    ).value
    second_game = tokens.issue_game(
        game_id=game_id,
        user_id=second_id,
        role=GameRole.PLAYER.value,
        color="b",
        now_ms=2000,
    ).value
    lifecycle.register_game(
        game_id,
        mode,
        (
            (first_id, PlayerSeat.FIRST_PLAYER),
            (second_id, PlayerSeat.SECOND_PLAYER),
        ),
        ranked=ranked,
        initial_state=GameLifecycleState.ACTIVE,
        now_ms=2000,
    )
    return {
        "game_id": game_id,
        "first_id": first_id,
        "first_auth": first_auth,
        "first_game": first_game,
        "second_id": second_id,
        "second_auth": second_auth,
        "second_game": second_game,
    }


def test_single_disconnect_and_same_player_reconnect_resumes_same_seat(tmp_path):
    values = system(tmp_path)
    _, _, tokens, _, _, _, lifecycle, controls = values
    game = active_game(values)

    paused = lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )
    reconnected = lifecycle.reconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=22999
    )

    assert paused.state is GameLifecycleState.PAUSED_FOR_RECONNECT
    assert paused.reconnect_deadline_ms == 23000
    assert game["game_id"] not in controls.paused
    assert reconnected.state is GameLifecycleState.ACTIVE
    first = next(item for item in reconnected.players if item.user_id == game["first_id"])
    assert first.seat is PlayerSeat.FIRST_PLAYER
    assert first.connected is True
    restored = tokens.verify_game(
        game["first_game"], game_id=game["game_id"], now_ms=23001
    )
    assert restored is not None and restored.status == "ACTIVE"


def test_play_timeout_with_meaningful_activity_is_rated_forfeit(tmp_path):
    values = system(tmp_path)
    database, users, tokens, _, _, _, lifecycle, controls = values
    game = active_game(values)
    assert lifecycle.record_accepted_command(game["game_id"], game["first_id"])
    lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )

    ended = lifecycle.expire(now_ms=23000)

    assert len(ended) == 1
    assert ended[0].state is GameLifecycleState.ENDED
    assert ended[0].terminal_reason == "forfeit"
    assert ended[0].winner_seat is PlayerSeat.SECOND_PLAYER
    assert users.by_id(game["first_id"]).rating == 1184
    assert users.by_id(game["second_id"]).rating == 1216
    assert tokens.verify_game(
        game["second_game"], game_id=game["game_id"], now_ms=23000
    ) is None
    assert game["game_id"] in controls.paused
    with database.transaction() as connection:
        result = connection.execute(
            "SELECT outcome, reason, ranked FROM game_results WHERE game_id = ?",
            (game["game_id"],),
        ).fetchone()
    assert tuple(result) == ("BLACK_WIN", "forfeit", 1)


def test_play_timeout_without_activity_cancels_without_elo(tmp_path):
    values = system(tmp_path)
    _, users, tokens, _, _, _, lifecycle, _ = values
    game = active_game(values)
    lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )

    cancelled = lifecycle.expire(now_ms=23000)[0]

    assert cancelled.state is GameLifecycleState.CANCELLED
    assert cancelled.terminal_reason == "no_meaningful_activity"
    assert users.by_id(game["first_id"]).rating == 1200
    assert users.by_id(game["second_id"]).rating == 1200
    assert tokens.verify_game(
        game["first_game"], game_id=game["game_id"], now_ms=23000
    ) is None


def test_room_disconnect_timeout_is_forfeit_but_never_rated(tmp_path):
    values = system(tmp_path)
    _, users, _, _, _, _, lifecycle, _ = values
    game = active_game(values, mode=GameMode.ROOM, ranked=False)
    lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )

    ended = lifecycle.expire(now_ms=23000)[0]

    assert ended.state is GameLifecycleState.ENDED
    assert ended.terminal_reason == "forfeit"
    assert users.by_id(game["first_id"]).rating == 1200
    assert users.by_id(game["second_id"]).rating == 1200


def test_double_disconnect_one_returning_still_cancels_without_elo(tmp_path):
    values = system(tmp_path)
    _, users, _, _, _, _, lifecycle, _ = values
    game = active_game(values)
    lifecycle.record_accepted_command(game["game_id"], game["first_id"])
    lifecycle.record_accepted_command(game["game_id"], game["second_id"])
    lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )
    lifecycle.disconnect(
        game["second_auth"], game["second_game"], game["game_id"], now_ms=3001
    )
    still_paused = lifecycle.reconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=4000
    )

    cancelled = lifecycle.expire(now_ms=23001)[0]

    assert still_paused.state is GameLifecycleState.PAUSED_FOR_RECONNECT
    assert cancelled.state is GameLifecycleState.CANCELLED
    assert cancelled.terminal_reason == "double_disconnect"
    assert users.by_id(game["first_id"]).rating == 1200
    assert users.by_id(game["second_id"]).rating == 1200


def test_both_disconnected_players_return_before_deadlines_and_resume(tmp_path):
    values = system(tmp_path)
    _, _, _, _, _, _, lifecycle, controls = values
    game = active_game(values)
    lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )
    lifecycle.disconnect(
        game["second_auth"], game["second_game"], game["game_id"], now_ms=3001
    )
    lifecycle.reconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=4000
    )
    resumed = lifecycle.reconnect(
        game["second_auth"], game["second_game"], game["game_id"], now_ms=4001
    )

    assert resumed.state is GameLifecycleState.ACTIVE
    assert all(item.connected for item in resumed.players)
    assert game["game_id"] not in controls.paused
    assert lifecycle.expire(now_ms=24000) == ()


def test_duplicate_game_over_event_updates_elo_exactly_once(tmp_path):
    values = system(tmp_path)
    database, users, _, _, _, _, lifecycle, _ = values
    game = active_game(values)
    event = GameOverEvent("w", captured_piece_id=9, ended_at_ms=5000)

    first = lifecycle.consume_game_over(game["game_id"], event)
    duplicate = lifecycle.consume_game_over(game["game_id"], event)

    assert first.state is GameLifecycleState.ENDED
    assert first.winner_seat is PlayerSeat.FIRST_PLAYER
    assert duplicate.changed is False
    assert users.by_id(game["first_id"]).rating == 1216
    assert users.by_id(game["second_id"]).rating == 1184
    with database.transaction() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM game_results WHERE game_id = ?", (game["game_id"],)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM rating_changes WHERE game_id = ?", (game["game_id"],)
        ).fetchone()[0] == 2


def test_spectator_token_cannot_reconnect_into_player_seat(tmp_path):
    values = system(tmp_path)
    _, _, tokens, auth, _, _, lifecycle, _ = values
    game = active_game(values)
    spectator_id, spectator_auth = player(auth, "Viewer", now_ms=1200)
    spectator_game = tokens.issue_game(
        game_id=game["game_id"],
        user_id=spectator_id,
        role=GameRole.SPECTATOR.value,
        color=None,
        now_ms=2000,
    ).value
    lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )

    with pytest.raises(GameLifecycleError) as forbidden:
        lifecycle.reconnect(
            spectator_auth, spectator_game, game["game_id"], now_ms=4000
        )
    assert forbidden.value.code is ProtocolErrorCode.FORBIDDEN


def test_restart_recovery_interrupts_active_revokes_game_tokens_not_auth(tmp_path):
    values = system(tmp_path)
    _, users, tokens, auth, repo, _, lifecycle, _ = values
    game = active_game(values)

    recovered = lifecycle.recover_after_restart(now_ms=5000)

    assert len(recovered) == 1
    assert recovered[0].state is GameLifecycleState.INTERRUPTED
    assert repo.by_id(game["game_id"]).terminal_reason == "server_restart"
    assert tokens.verify_game(
        game["first_game"], game_id=game["game_id"], now_ms=5000
    ) is None
    assert auth.validate_auth_token(game["first_auth"], now_ms=5000).user_id == game["first_id"]
    assert users.by_id(game["first_id"]).rating == 1200


def test_matchmaking_registers_active_play_and_room_auto_starts_on_join(tmp_path):
    values = system(tmp_path)
    _, _, tokens, auth, repo, rooms_repo, lifecycle, _ = values
    _, first = player(auth, "PlayOne")
    _, second = player(auth, "PlayTwo", now_ms=1100)
    matchmaking = MatchmakingService(
        auth,
        tokens,
        rating_range=100,
        timeout_seconds=60,
        max_queue_users=10,
        seat_selector=lambda waiting, joining: (waiting, joining),
        game_id_factory=lambda: "play-game",
        lifecycle_service=lifecycle,
    )
    matchmaking.join(first, now_ms=2000)
    matchmaking.join(second, now_ms=2001)
    assert repo.by_id("play-game").state == "ACTIVE"

    _, creator = player(auth, "RoomOne", now_ms=1200)
    _, opponent = player(auth, "RoomTwo", now_ms=1300)
    rooms = RoomsService(
        auth,
        tokens,
        rooms_repo,
        max_spectators=10,
        max_open_rooms=10,
        code_factory=lambda: "ABC234",
        game_id_factory=lambda: "room-game",
        lifecycle_service=lifecycle,
    )
    created = rooms.create(creator, now_ms=2100)
    joined = rooms.join(opponent, created.code, now_ms=2101)

    assert repo.by_id("room-game").state == "ACTIVE"
    assert rooms_repo.by_id(created.room_id).started_at_ms == 2101
    assert joined.gameplay_started is True


def test_room_opponent_leave_after_start_is_deferred(tmp_path):
    values = system(tmp_path)
    _, _, tokens, auth, repo, rooms_repo, lifecycle, _ = values
    _, creator = player(auth, "RoomOne")
    _, opponent = player(auth, "RoomTwo", now_ms=1100)
    rooms = RoomsService(
        auth,
        tokens,
        rooms_repo,
        max_spectators=10,
        max_open_rooms=10,
        code_factory=lambda: "ABC234",
        game_id_factory=lambda: "room-game",
        lifecycle_service=lifecycle,
    )
    created = rooms.create(creator, now_ms=2000)
    joined = rooms.join(opponent, created.code, now_ms=2001)
    assert joined.gameplay_started is True
    assert repo.by_id("room-game").state == "ACTIVE"

    left = rooms.leave(opponent, created.code, now_ms=2002)
    assert left.leave_deferred is True


def test_technical_draw_uses_elo_draw_and_is_idempotent(tmp_path):
    values = system(tmp_path)
    _, users, _, _, _, _, lifecycle, _ = values
    game = active_game(values)

    ended = lifecycle.finalize_result(
        game["game_id"],
        "draw",
        reason="technical_draw",
        now_ms=5000,
    )
    duplicate = lifecycle.finalize_result(
        game["game_id"],
        "draw",
        reason="technical_draw",
        now_ms=5001,
    )

    assert ended.state is GameLifecycleState.ENDED
    assert ended.winner_seat is None
    assert duplicate.changed is False
    assert users.by_id(game["first_id"]).rating == 1200
    assert users.by_id(game["second_id"]).rating == 1200


def test_created_waiting_active_cancelled_and_interrupted_transitions(tmp_path):
    values = system(tmp_path)
    _, _, _, auth, _, _, lifecycle, _ = values
    first_id, _ = player(auth, "StateOne")
    second_id, _ = player(auth, "StateTwo", now_ms=1100)
    players = (
        (first_id, PlayerSeat.FIRST_PLAYER),
        (second_id, PlayerSeat.SECOND_PLAYER),
    )

    created = lifecycle.register_game(
        "state-game",
        GameMode.PLAY,
        players,
        ranked=False,
        now_ms=2000,
    )
    duplicate = lifecycle.register_game(
        "state-game",
        GameMode.PLAY,
        players,
        ranked=False,
        now_ms=2000,
    )
    waiting = lifecycle.mark_waiting_to_start("state-game", now_ms=2001)
    active = lifecycle.activate_game("state-game", now_ms=2002)
    cancelled = lifecycle.cancel(
        "state-game", reason="operator_cancelled", now_ms=2003
    )
    duplicate_cancel = lifecycle.cancel(
        "state-game", reason="operator_cancelled", now_ms=2004
    )

    assert created.state is GameLifecycleState.CREATED
    assert duplicate.changed is False
    assert waiting.state is GameLifecycleState.WAITING_TO_START
    assert active.state is GameLifecycleState.ACTIVE
    assert cancelled.state is GameLifecycleState.CANCELLED
    assert duplicate_cancel.changed is False

    lifecycle.register_game(
        "interrupt-game",
        GameMode.PLAY,
        players,
        ranked=False,
        initial_state=GameLifecycleState.ACTIVE,
        now_ms=2100,
    )
    interrupted = lifecycle.interrupt("interrupt-game", now_ms=2101)
    assert interrupted.state is GameLifecycleState.INTERRUPTED


def test_invalid_lifecycle_registration_and_activation_are_rejected(tmp_path):
    values = system(tmp_path)
    _, _, _, auth, _, _, lifecycle, _ = values
    first_id, _ = player(auth, "OnlyOne")

    with pytest.raises(GameLifecycleError) as ranked_room:
        lifecycle.register_game(
            "invalid-room",
            GameMode.ROOM,
            ((first_id, PlayerSeat.FIRST_PLAYER),),
            ranked=True,
            now_ms=2000,
        )
    assert ranked_room.value.code is ProtocolErrorCode.INVALID_GAME_STATE

    lifecycle.register_game(
        "one-player",
        GameMode.PLAY,
        ((first_id, PlayerSeat.FIRST_PLAYER),),
        ranked=False,
        now_ms=2000,
    )
    with pytest.raises(GameLifecycleError) as activation:
        lifecycle.activate_game("one-player", now_ms=2001)
    assert activation.value.code is ProtocolErrorCode.INVALID_GAME_STATE


def test_reconnect_at_deadline_is_expired_and_event_subscriber_finalizes_once(tmp_path):
    values = system(tmp_path)
    _, _, _, _, _, _, lifecycle, _ = values
    game = active_game(values)
    lifecycle.disconnect(
        game["first_auth"], game["first_game"], game["game_id"], now_ms=3000
    )

    with pytest.raises(GameLifecycleError) as expired:
        lifecycle.reconnect(
            game["first_auth"], game["first_game"], game["game_id"], now_ms=23000
        )
    assert expired.value.code is ProtocolErrorCode.RECONNECT_EXPIRED

    second_values = system(tmp_path / "subscriber")
    second_game = active_game(second_values)
    second_lifecycle = second_values[6]
    subscriber = second_lifecycle.subscriber_for(second_game["game_id"])
    event = GameOverEvent("b", captured_piece_id=12, ended_at_ms=5000)
    subscriber.handle(event)
    subscriber.handle(event)
    assert second_values[4].by_id(second_game["game_id"]).state == "ENDED"


def route(router, message_type, payload, request_id="request-1"):
    envelope = MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": message_type,
            "request_id": request_id,
            "timestamp_ms": 1,
            "payload": payload,
        },
        POLICY,
    )
    return asyncio.run(router.route(RequestContext("connection-1", envelope)))


def test_lifecycle_routing_returns_countdown_resume_and_no_tokens(tmp_path):
    values = system(tmp_path)
    _, _, _, _, _, _, lifecycle, _ = values
    game = active_game(values)
    current_time = {"ms": 3000}
    router = MessageRouter()
    GameLifecycleHandlers(
        lifecycle, clock_ms=lambda: current_time["ms"]
    ).register_routes(router)
    payload = {
        "auth_token": game["first_auth"],
        "game_token": game["first_game"],
        "game_id": game["game_id"],
    }

    disconnected = route(router, "game_disconnect", payload)
    current_time["ms"] = 4000
    reconnected = route(router, "game_reconnect", payload, "request-2")

    assert disconnected.type == "disconnect_countdown"
    assert disconnected.payload["remaining_ms"] == 20000
    assert disconnected.payload["state"] == "PAUSED_FOR_RECONNECT"
    assert reconnected.type == "game_lifecycle_status"
    assert reconnected.payload["state"] == "ACTIVE"
    assert "game_token" not in disconnected.payload
    assert "auth_token" not in disconnected.payload


def test_lifecycle_status_route_emits_cancelled_at_grace_deadline(tmp_path):
    values = system(tmp_path)
    _, _, _, _, _, _, lifecycle, _ = values
    game = active_game(values)
    current_time = {"ms": 3000}
    router = MessageRouter()
    GameLifecycleHandlers(
        lifecycle, clock_ms=lambda: current_time["ms"]
    ).register_routes(router)
    payload = {
        "auth_token": game["first_auth"],
        "game_token": game["first_game"],
        "game_id": game["game_id"],
    }
    route(router, "game_disconnect", payload)

    current_time["ms"] = 23000
    cancelled = route(router, "game_lifecycle_status", payload, "request-2")

    assert cancelled.type == "game_cancelled"
    assert cancelled.payload["reason"] == "no_meaningful_activity"
    assert cancelled.payload["state"] == "CANCELLED"


def test_lifecycle_status_route_emits_forfeit_winner_at_grace_deadline(tmp_path):
    values = system(tmp_path)
    _, _, _, _, _, _, lifecycle, _ = values
    game = active_game(values)
    lifecycle.record_accepted_command(game["game_id"], game["first_id"])
    current_time = {"ms": 3000}
    router = MessageRouter()
    GameLifecycleHandlers(
        lifecycle, clock_ms=lambda: current_time["ms"]
    ).register_routes(router)
    payload = {
        "auth_token": game["first_auth"],
        "game_token": game["first_game"],
        "game_id": game["game_id"],
    }
    route(router, "game_disconnect", payload)

    current_time["ms"] = 23000
    forfeited = route(router, "game_lifecycle_status", payload, "request-2")

    assert forfeited.type == "game_forfeit"
    assert forfeited.payload["winner_seat"] == "SECOND_PLAYER"
    assert forfeited.payload["winner_color"] == "b"


def test_lifecycle_routes_validate_payload_and_return_structured_errors(tmp_path):
    values = system(tmp_path)
    _, _, _, _, _, _, lifecycle, _ = values
    router = MessageRouter()
    GameLifecycleHandlers(lifecycle, clock_ms=lambda: 3000).register_routes(router)

    failed = route(
        router,
        "game_disconnect",
        {"auth_token": "invalid", "game_token": "invalid", "game_id": "missing"},
    )
    assert failed.type == "command_result"
    assert failed.payload == {"accepted": False, "code": "invalid_token"}

    with pytest.raises(ProtocolError) as raised:
        route(
            router,
            "game_reconnect",
            {"auth_token": "invalid", "game_id": "missing"},
            "request-2",
        )
    assert raised.value.code is ProtocolErrorCode.INVALID_FIELD
