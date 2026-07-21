import sqlite3

from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameTokenRepository,
    MatchRepository,
    RoomRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)


def persistence(tmp_path):
    path = tmp_path / "kfchess.sqlite3"
    database = SqliteDatabase(path, busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    auth = AuthSessionRepository(database)
    game_tokens = GameTokenRepository(database)
    return path, database, users, auth, game_tokens


def create_user(users, username, now_ms=1000):
    return users.create(
        username=username,
        password_hash=f"hash-for-{username}",
        email=f"{username}@Example.Test",
        phone="+972 50-123-4567",
        initial_rating=1200,
        now_ms=now_ms,
    )


def test_migrations_are_repeatable_and_create_required_tables(tmp_path):
    path, database, *_ = persistence(tmp_path)
    database.migrate()

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "users", "auth_sessions", "game_session_tokens", "game_results",
        "rating_changes", "rooms", "room_members", "schema_migrations",
    }.issubset(tables)


def test_users_are_case_sensitive_and_private_fields_are_normalized(tmp_path):
    _, _, users, *_ = persistence(tmp_path)
    upper = create_user(users, "Dana")
    lower = create_user(users, "dana", now_ms=1001)

    assert upper.id != lower.id
    assert users.by_username("Dana").email == "dana@example.test"
    assert users.by_username("DANA") is None
    assert users.by_username("Dana").phone == "+972501234567"


def test_auth_token_is_hashed_expires_and_can_be_revoked(tmp_path):
    path, _, users, auth, game_tokens = persistence(tmp_path)
    user = create_user(users, "Dana")
    service = TokenService(auth, game_tokens, token_bytes=32)

    issued = service.issue_auth(user_id=user.id, now_ms=2000, ttl_seconds=60)

    assert service.verify_auth(issued.value, now_ms=3000).user_id == user.id
    assert service.verify_auth(issued.value, now_ms=62000) is None
    with sqlite3.connect(path) as connection:
        stored = connection.execute("SELECT token_hash FROM auth_sessions").fetchone()[0]
    assert issued.value not in stored
    assert stored == service.hash_token(issued.value)
    assert service.revoke_auth(issued.value, now_ms=4000) is True
    assert service.verify_auth(issued.value, now_ms=5000) is None


def test_game_token_is_scoped_to_game_and_grace_window(tmp_path):
    _, _, users, auth, game_tokens = persistence(tmp_path)
    user = create_user(users, "Dana")
    service = TokenService(auth, game_tokens, token_bytes=32)
    issued = service.issue_game(
        game_id="game-1", user_id=user.id, role="PLAYER", color="w", now_ms=1000
    )

    assert service.verify_game(issued.value, game_id="game-2", now_ms=1001) is None
    assert service.begin_game_grace(issued.value, grace_expires_at_ms=21000) is True
    assert service.verify_game(issued.value, game_id="game-1", now_ms=21000).status == "GRACE"
    assert service.verify_game(issued.value, game_id="game-1", now_ms=21001) is None


def test_ranked_result_and_both_ratings_are_committed_once(tmp_path):
    _, database, users, *_ = persistence(tmp_path)
    white = create_user(users, "White")
    black = create_user(users, "Black")
    matches = MatchRepository(database)
    values = dict(
        game_id="game-1", white_user_id=white.id, black_user_id=black.id,
        outcome="WHITE_WIN", reason="king_captured",
        white_rating_before=1200, white_rating_after=1216,
        black_rating_before=1200, black_rating_after=1184, now_ms=5000,
    )

    assert matches.save_ranked_result(**values) is True
    assert matches.save_ranked_result(**values) is False
    assert users.by_id(white.id).rating == 1216
    assert users.by_id(black.id).rating == 1184
    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM game_results").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM rating_changes").fetchone()[0] == 2


def test_room_metadata_and_membership_history_are_persisted(tmp_path):
    _, database, users, *_ = persistence(tmp_path)
    creator = create_user(users, "Creator")
    rooms = RoomRepository(database)

    room = rooms.create(
        code="abc234",
        game_id="room-game-1",
        creator_user_id=creator.id,
        now_ms=1000,
    )
    member = rooms.add_member(
        room_id=room.id, user_id=creator.id, role="PLAYER", color="w", now_ms=1000
    )

    assert room.code == "ABC234"
    assert room.game_id == "room-game-1"
    assert rooms.leave_member(member.id, now_ms=2000) is True
    assert rooms.close(room.id, reason="host_left", now_ms=2000) is True
    with database.transaction() as connection:
        row = connection.execute("SELECT status, close_reason FROM rooms").fetchone()
    assert tuple(row) == ("CLOSED", "host_left")


def test_sqlite_backup_is_consistent_and_readable(tmp_path):
    _, database, users, *_ = persistence(tmp_path)
    create_user(users, "Dana")

    backup_path = database.backup_to(tmp_path / "backups", timestamp_ms=9000)

    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT username FROM users").fetchone()[0] == "Dana"
