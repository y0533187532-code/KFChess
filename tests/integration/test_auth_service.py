import sqlite3

import pytest

from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameTokenRepository,
    MatchRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from kongfu_chess.protocol import ProtocolErrorCode
from kongfu_chess.infrastructure import ConfigProvider
from kongfu_chess.server import (
    AuthError,
    AuthService,
    PasswordHasher,
    build_auth_service,
)


def auth_system(tmp_path):
    path = tmp_path / "auth.sqlite3"
    database = SqliteDatabase(path, busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    auth_sessions = AuthSessionRepository(database)
    tokens = TokenService(
        auth_sessions, GameTokenRepository(database), token_bytes=32
    )
    passwords = PasswordHasher(
        salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32
    )
    service = AuthService(
        users,
        tokens,
        passwords,
        password_min_length=6,
        initial_rating=1200,
        auth_token_ttl_seconds=60,
    )
    return path, database, users, service


def register(service, username="Dana", now_ms=1000):
    return service.register(
        username=username,
        password="secret7",
        email=f"{username}@Example.Test",
        phone="+972 50-123-4567",
        now_ms=now_ms,
    )


def assert_auth_error(code, action):
    with pytest.raises(AuthError) as raised:
        action()
    assert raised.value.code is code


def test_register_hashes_password_normalizes_private_fields_and_is_case_sensitive(tmp_path):
    path, _, users, service = auth_system(tmp_path)

    upper = register(service, "Dana")
    lower = register(service, "dana", now_ms=1001)

    assert upper.rating == lower.rating == 1200
    stored = users.by_username("Dana")
    assert stored.email == "dana@example.test"
    assert stored.phone == "+972501234567"
    assert stored.password_hash.startswith("scrypt$1$")
    assert "secret7" not in stored.password_hash
    with sqlite3.connect(path) as connection:
        serialized = "|".join(str(value) for value in connection.execute(
            "SELECT password_hash, email, phone FROM users WHERE id = ?", (upper.user_id,)
        ).fetchone())
    assert "secret7" not in serialized


def test_registration_returns_specific_validation_codes(tmp_path):
    _, _, _, service = auth_system(tmp_path)

    assert_auth_error(
        ProtocolErrorCode.PASSWORD_TOO_SHORT,
        lambda: service.register(
            username="Dana", password="short", email="d@example.test",
            phone="0501234567", now_ms=1,
        ),
    )
    assert_auth_error(
        ProtocolErrorCode.INVALID_USERNAME,
        lambda: service.register(
            username="bad name", password="secret7", email="d@example.test",
            phone="0501234567", now_ms=1,
        ),
    )
    register(service)
    assert_auth_error(
        ProtocolErrorCode.USERNAME_TAKEN,
        lambda: register(service, now_ms=1002),
    )


def test_login_is_case_sensitive_replaces_old_session_and_returns_raw_token_once(tmp_path):
    path, _, _, service = auth_system(tmp_path)
    account = register(service)

    assert_auth_error(
        ProtocolErrorCode.INVALID_CREDENTIALS,
        lambda: service.login(username="dana", password="secret7", now_ms=2000),
    )
    first = service.login(username="Dana", password="secret7", now_ms=2000)
    second = service.login(username="Dana", password="secret7", now_ms=3000)

    assert first.user_id == second.user_id == account.user_id
    assert first.auth_token != second.auth_token
    assert_auth_error(
        ProtocolErrorCode.TOKEN_REVOKED,
        lambda: service.validate_auth_token(first.auth_token, now_ms=3001),
    )
    assert service.validate_auth_token(second.auth_token, now_ms=3001).username == "Dana"
    with sqlite3.connect(path) as connection:
        stored_hashes = [row[0] for row in connection.execute(
            "SELECT token_hash FROM auth_sessions"
        )]
    assert first.auth_token not in stored_hashes
    assert second.auth_token not in stored_hashes


def test_token_expiry_logout_and_invalid_token_have_stable_codes(tmp_path):
    _, _, _, service = auth_system(tmp_path)
    register(service)
    expired = service.login(username="Dana", password="secret7", now_ms=1000)
    assert_auth_error(
        ProtocolErrorCode.TOKEN_EXPIRED,
        lambda: service.validate_auth_token(expired.auth_token, now_ms=61000),
    )

    current = service.login(username="Dana", password="secret7", now_ms=62000)
    service.logout(current.auth_token, now_ms=62001)
    assert_auth_error(
        ProtocolErrorCode.TOKEN_REVOKED,
        lambda: service.validate_auth_token(current.auth_token, now_ms=62002),
    )
    assert_auth_error(
        ProtocolErrorCode.INVALID_TOKEN,
        lambda: service.validate_auth_token("unknown", now_ms=62002),
    )


def test_anonymize_removes_identity_revokes_token_and_keeps_match_result(tmp_path):
    _, database, users, service = auth_system(tmp_path)
    dana = register(service, "Dana")
    opponent = register(service, "Opponent", now_ms=1001)
    MatchRepository(database).save_ranked_result(
        game_id="game-1",
        white_user_id=dana.user_id,
        black_user_id=opponent.user_id,
        outcome="WHITE_WIN",
        reason="king_captured",
        white_rating_before=1200,
        white_rating_after=1216,
        black_rating_before=1200,
        black_rating_after=1184,
        now_ms=2000,
    )
    session = service.login(username="Dana", password="secret7", now_ms=3000)

    assert service.anonymize_account(session.auth_token, now_ms=4000) == dana.user_id

    anonymized = users.by_id(dana.user_id)
    assert anonymized.status == "ANONYMIZED"
    assert anonymized.username.startswith("deleted_")
    assert anonymized.password_hash == ""
    assert anonymized.email is anonymized.phone is None
    assert_auth_error(
        ProtocolErrorCode.TOKEN_REVOKED,
        lambda: service.validate_auth_token(session.auth_token, now_ms=4001),
    )
    with database.transaction() as connection:
        result = connection.execute(
            "SELECT game_id, white_user_id FROM game_results"
        ).fetchone()
    assert tuple(result) == ("game-1", dana.user_id)


def test_auth_composition_uses_external_configuration(tmp_path):
    config = ConfigProvider.load("config/server.json")
    database = SqliteDatabase(tmp_path / "composed.sqlite3", busy_timeout_ms=1000)
    database.migrate()
    service = build_auth_service(database, config)

    account = service.register(
        username="ConfiguredUser",
        password="secret7",
        email="configured@example.test",
        phone="0501234567",
        now_ms=1000,
    )
    session = service.login(
        username="ConfiguredUser", password="secret7", now_ms=2000
    )

    assert account.rating == config.elo.initial_rating
    assert session.expires_at_ms == (
        2000 + config.timing.auth_token_ttl_seconds * 1000
    )
