import pytest

from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameLifecycleRepository,
    GameTokenRepository,
    MatchRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from kongfu_chess.protocol import ProtocolErrorCode
from kongfu_chess.server import (
    AuthError,
    AuthService,
    EloService,
    GameLifecycleService,
    MatchmakingError,
    MatchmakingService,
    PasswordHasher,
    PlayerSeat,
)


def system(tmp_path, *, max_queue_users=200):
    database = SqliteDatabase(tmp_path / "matchmaking.sqlite3", busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    auth_sessions = AuthSessionRepository(database)
    game_tokens = GameTokenRepository(database)
    tokens = TokenService(auth_sessions, game_tokens, token_bytes=32)
    auth = AuthService(
        users,
        tokens,
        PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32),
        password_min_length=6,
        initial_rating=1200,
        auth_token_ttl_seconds=600,
    )
    matchmaking = MatchmakingService(
        auth,
        tokens,
        rating_range=100,
        timeout_seconds=60,
        max_queue_users=max_queue_users,
        seat_selector=lambda waiting, joining: (waiting, joining),
        game_id_factory=lambda: "game-1",
    )
    return database, users, tokens, auth, matchmaking


def player(database, auth, username, *, rating=1200, now_ms=1000):
    account = auth.register(
        username=username,
        password="secret7",
        email=f"{username}@example.test",
        phone="0501234567",
        now_ms=now_ms,
    )
    with database.transaction() as connection:
        connection.execute(
            "UPDATE users SET rating = ? WHERE id = ?", (rating, account.user_id)
        )
    session = auth.login(username=username, password="secret7", now_ms=now_ms + 1)
    return account.user_id, session.auth_token


def test_only_authenticated_user_can_join_and_duplicate_ticket_is_rejected(tmp_path):
    database, _, _, auth, matchmaking = system(tmp_path)
    _, token = player(database, auth, "Dana")

    with pytest.raises(AuthError) as invalid:
        matchmaking.join("not-a-token", now_ms=2000)
    assert invalid.value.code is ProtocolErrorCode.INVALID_TOKEN

    queued = matchmaking.join(token, now_ms=2000)
    assert queued.state == "QUEUED"
    with pytest.raises(MatchmakingError) as duplicate:
        matchmaking.join(token, now_ms=2001)
    assert duplicate.value.code is ProtocolErrorCode.ALREADY_IN_MATCHMAKING


def test_inclusive_rating_range_creates_ranked_play_match_and_game_tokens(tmp_path):
    database, _, tokens, auth, matchmaking = system(tmp_path)
    first_id, first_token = player(database, auth, "First", rating=1200)
    second_id, second_token = player(
        database, auth, "Second", rating=1300, now_ms=1100
    )

    assert matchmaking.join(first_token, now_ms=2000).state == "QUEUED"
    found = matchmaking.join(second_token, now_ms=2001)
    waiting_view = matchmaking.status(first_token, now_ms=2002).match
    match = matchmaking.match_by_id("game-1")

    assert found.state == "MATCH_FOUND"
    assert match.ranked is True
    assert match.mode == "PLAY"
    assert match.first_player.user_id == first_id
    assert match.second_player.user_id == second_id
    assert found.match.seat is PlayerSeat.SECOND_PLAYER
    assert waiting_view.seat is PlayerSeat.FIRST_PLAYER
    assert found.match.game_token != waiting_view.game_token
    assert tokens.verify_game(
        found.match.game_token, game_id="game-1", now_ms=2002
    ).user_id == second_id
    assert tokens.verify_game(
        waiting_view.game_token, game_id="game-1", now_ms=2002
    ).user_id == first_id
    assert tokens.verify_game(
        found.match.game_token, game_id="game-1", now_ms=2002
    ).color == "b"
    assert tokens.verify_game(
        waiting_view.game_token, game_id="game-1", now_ms=2002
    ).color == "w"


def test_oldest_compatible_ticket_wins_among_multiple_candidates(tmp_path):
    database, _, _, auth, matchmaking = system(tmp_path)
    oldest_id, oldest = player(database, auth, "Oldest", rating=1300)
    newer_id, newer = player(database, auth, "Newer", rating=1100, now_ms=1100)
    joiner_id, joiner = player(database, auth, "Joiner", rating=1200, now_ms=1200)

    matchmaking.join(oldest, now_ms=2000)
    matchmaking.join(newer, now_ms=2001)
    found = matchmaking.join(joiner, now_ms=2002)

    assert found.match.user_id == joiner_id
    assert found.match.opponent_user_id == oldest_id
    assert matchmaking.queued_user_ids == (newer_id,)


def test_release_game_clears_matchmaking_entries(tmp_path):
    database, _, _, auth, matchmaking = system(tmp_path)
    first_id, first_token = player(database, auth, "First", rating=1200)
    second_id, second_token = player(
        database, auth, "Second", rating=1300, now_ms=1100
    )

    matchmaking.join(first_token, now_ms=2000)
    matchmaking.join(second_token, now_ms=2001)

    assert first_id in matchmaking._matches_by_user
    assert second_id in matchmaking._matches_by_user
    matchmaking.release_game("game-1")
    assert first_id not in matchmaking._matches_by_user
    assert second_id not in matchmaking._matches_by_user
    assert matchmaking.match_by_id("game-1") is None


def test_play_queue_join_allowed_after_terminal_game(tmp_path):
    database = SqliteDatabase(tmp_path / "matchmaking-release.sqlite3", busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    auth_sessions = AuthSessionRepository(database)
    game_tokens = GameTokenRepository(database)
    tokens = TokenService(auth_sessions, game_tokens, token_bytes=32)
    auth = AuthService(
        users,
        tokens,
        PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32),
        password_min_length=6,
        initial_rating=1200,
        auth_token_ttl_seconds=600,
    )
    lifecycle = GameLifecycleService(
        auth,
        tokens,
        GameLifecycleRepository(database),
        users,
        MatchRepository(database),
        EloService(scale=400, k_factor=32, rating_floor=100),
        reconnect_grace_seconds=20,
    )
    matchmaking = MatchmakingService(
        auth,
        tokens,
        rating_range=100,
        timeout_seconds=60,
        max_queue_users=200,
        seat_selector=lambda waiting, joining: (waiting, joining),
        game_id_factory=lambda: "game-1",
        lifecycle_service=lifecycle,
    )
    lifecycle.set_terminal_listener(matchmaking.release_game)

    first_id, first_token = player(database, auth, "First", rating=1200)
    second_id, second_token = player(
        database, auth, "Second", rating=1300, now_ms=1100
    )
    matchmaking.join(first_token, now_ms=2000)
    found = matchmaking.join(second_token, now_ms=2001)
    match = matchmaking.match_by_id("game-1")
    first_game = next(
        seat.game_token for seat in match.seats if seat.user_id == first_id
    )

    lifecycle.resign(first_token, first_game, "game-1", now_ms=3000)

    assert lifecycle.user_in_active_game(first_id) is False
    assert first_id not in matchmaking._matches_by_user
    rejoined = matchmaking.join(first_token, now_ms=4000)
    assert rejoined.state == "QUEUED"
    assert found.match.user_id == second_id


def test_timeout_is_inclusive_and_cancel_or_disconnect_remove_without_elo_change(tmp_path):
    database, users, _, auth, matchmaking = system(tmp_path)
    timed_id, timed = player(database, auth, "Timed")
    cancel_id, cancel = player(database, auth, "Cancel", rating=1500, now_ms=1100)
    disconnect_id, disconnect = player(
        database, auth, "Disconnect", rating=1800, now_ms=1200
    )

    matchmaking.join(timed, now_ms=2000)
    assert matchmaking.status(timed, now_ms=61999).state == "QUEUED"
    assert matchmaking.status(timed, now_ms=62000).state == "TIMED_OUT"

    matchmaking.join(cancel, now_ms=70000)
    assert matchmaking.cancel(cancel, now_ms=70001).state == "IDLE"
    matchmaking.join(disconnect, now_ms=70002)
    assert matchmaking.disconnect_user(disconnect_id) is True
    assert matchmaking.queued_user_ids == ()
    assert users.by_id(timed_id).rating == 1200
    assert users.by_id(cancel_id).rating == 1500
    assert users.by_id(disconnect_id).rating == 1800


def test_queue_capacity_is_enforced_from_configuration_value(tmp_path):
    database, _, _, auth, matchmaking = system(tmp_path, max_queue_users=1)
    _, first = player(database, auth, "First", rating=1000)
    _, second = player(database, auth, "Second", rating=1300, now_ms=1100)

    matchmaking.join(first, now_ms=2000)
    with pytest.raises(MatchmakingError) as full:
        matchmaking.join(second, now_ms=2001)
    assert full.value.code is ProtocolErrorCode.MATCHMAKING_QUEUE_FULL
