"""Application service for account lifecycle and authentication sessions."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..protocol import ProtocolErrorCode


class AuthError(ValueError):
    def __init__(self, code: ProtocolErrorCode):
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class RegisteredAccount:
    user_id: int
    username: str
    rating: int


@dataclass(frozen=True)
class AuthenticatedSession:
    user_id: int
    username: str
    rating: int
    auth_token: str
    expires_at_ms: int


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: int
    username: str
    rating: int


class AuthService:
    def __init__(
        self,
        users,
        tokens,
        password_hasher,
        *,
        password_min_length: int,
        initial_rating: int,
        auth_token_ttl_seconds: int,
    ):
        self._users = users
        self._tokens = tokens
        self._password_hasher = password_hasher
        self._password_min_length = password_min_length
        self._initial_rating = initial_rating
        self._auth_token_ttl_seconds = auth_token_ttl_seconds

    def register(
        self,
        *,
        username: str,
        password: str,
        email: str,
        phone: str,
        now_ms: int,
    ) -> RegisteredAccount:
        if not isinstance(password, str) or len(password) < self._password_min_length:
            raise AuthError(ProtocolErrorCode.PASSWORD_TOO_SHORT)
        try:
            user = self._users.create(
                username=username,
                password_hash=self._password_hasher.hash(password),
                email=email,
                phone=phone,
                initial_rating=self._initial_rating,
                now_ms=now_ms,
            )
        except sqlite3.IntegrityError as exc:
            raise AuthError(ProtocolErrorCode.USERNAME_TAKEN) from exc
        except (TypeError, ValueError) as exc:
            raise AuthError(self._registration_error_code(exc)) from exc
        return RegisteredAccount(user.id, user.username, user.rating)

    def login(
        self, *, username: str, password: str, now_ms: int
    ) -> AuthenticatedSession:
        if not isinstance(username, str) or not isinstance(password, str):
            raise AuthError(ProtocolErrorCode.INVALID_CREDENTIALS)
        user = self._users.by_username(username)
        if user is None or not self._password_hasher.verify(
            password, user.password_hash
        ):
            raise AuthError(ProtocolErrorCode.INVALID_CREDENTIALS)
        if user.status != "ACTIVE":
            raise AuthError(ProtocolErrorCode.ACCOUNT_DISABLED)

        self._tokens.revoke_user_auth(user.id, now_ms=now_ms)
        issued = self._tokens.issue_auth(
            user_id=user.id,
            now_ms=now_ms,
            ttl_seconds=self._auth_token_ttl_seconds,
        )
        return AuthenticatedSession(
            user.id,
            user.username,
            user.rating,
            issued.value,
            issued.expires_at_ms,
        )

    def logout(self, auth_token: str, *, now_ms: int) -> None:
        self._require_valid_session(auth_token, now_ms=now_ms)
        if not self._tokens.revoke_auth(auth_token, now_ms=now_ms):
            raise AuthError(ProtocolErrorCode.INVALID_TOKEN)

    def validate_auth_token(
        self, auth_token: str, *, now_ms: int
    ) -> AuthPrincipal:
        session = self._require_valid_session(auth_token, now_ms=now_ms)
        user = self._users.by_id(session.user_id)
        if user is None:
            raise AuthError(ProtocolErrorCode.INVALID_TOKEN)
        if user.status != "ACTIVE":
            raise AuthError(ProtocolErrorCode.ACCOUNT_DISABLED)
        return AuthPrincipal(user.id, user.username, user.rating)

    def anonymize_account(
        self, auth_token: str, *, now_ms: int
    ) -> int:
        principal = self.validate_auth_token(auth_token, now_ms=now_ms)
        if not self._users.anonymize(principal.user_id, now_ms=now_ms):
            raise AuthError(ProtocolErrorCode.ACCOUNT_DISABLED)
        return principal.user_id

    def _require_valid_session(self, auth_token: str, *, now_ms: int):
        if not isinstance(auth_token, str) or not auth_token:
            raise AuthError(ProtocolErrorCode.INVALID_TOKEN)
        validation = self._tokens.validate_auth(auth_token, now_ms=now_ms)
        if validation.status == "EXPIRED":
            raise AuthError(ProtocolErrorCode.TOKEN_EXPIRED)
        if validation.status == "REVOKED":
            raise AuthError(ProtocolErrorCode.TOKEN_REVOKED)
        if validation.status != "VALID" or validation.session is None:
            raise AuthError(ProtocolErrorCode.INVALID_TOKEN)
        return validation.session

    @staticmethod
    def _registration_error_code(error: Exception) -> ProtocolErrorCode:
        detail = str(error)
        if "username" in detail:
            return ProtocolErrorCode.INVALID_USERNAME
        if "email" in detail:
            return ProtocolErrorCode.INVALID_EMAIL
        if "phone" in detail:
            return ProtocolErrorCode.INVALID_PHONE
        return ProtocolErrorCode.INVALID_REGISTRATION


def build_auth_service(database, config) -> AuthService:
    """Compose authentication infrastructure exclusively from validated config."""
    from ..persistence import (
        AuthSessionRepository,
        GameTokenRepository,
        TokenService,
        UserRepository,
    )
    from .password_hasher import PasswordHasher

    users = UserRepository(
        database,
        username_min_length=config.security.username_min_length,
        username_max_length=config.security.username_max_length,
    )
    tokens = TokenService(
        AuthSessionRepository(database),
        GameTokenRepository(database),
        token_bytes=config.security.token_bytes,
    )
    passwords = PasswordHasher(
        salt_bytes=config.security.password_salt_bytes,
        n=config.security.scrypt_n,
        r=config.security.scrypt_r,
        p=config.security.scrypt_p,
        hash_bytes=config.security.password_hash_bytes,
    )
    return AuthService(
        users,
        tokens,
        passwords,
        password_min_length=config.security.password_min_length,
        initial_rating=config.elo.initial_rating,
        auth_token_ttl_seconds=config.timing.auth_token_ttl_seconds,
    )
