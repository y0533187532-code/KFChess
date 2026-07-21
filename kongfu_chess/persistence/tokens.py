"""Issue opaque tokens while persisting only deterministic hashes."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class IssuedToken:
    value: str
    expires_at_ms: int | None


class TokenService:
    def __init__(self, auth_sessions, game_tokens, *, token_bytes: int):
        self._auth_sessions = auth_sessions
        self._game_tokens = game_tokens
        self._token_bytes = token_bytes

    def issue_auth(
        self, *, user_id: int, now_ms: int, ttl_seconds: int
    ) -> IssuedToken:
        value = secrets.token_urlsafe(self._token_bytes)
        expires_at_ms = now_ms + ttl_seconds * 1000
        self._auth_sessions.create(
            user_id=user_id,
            token_hash=self.hash_token(value),
            now_ms=now_ms,
            expires_at_ms=expires_at_ms,
        )
        return IssuedToken(value, expires_at_ms)

    def verify_auth(self, value: str, *, now_ms: int):
        return self.validate_auth(value, now_ms=now_ms).session

    def validate_auth(self, value: str, *, now_ms: int):
        return self._auth_sessions.validate(self.hash_token(value), now_ms=now_ms)

    def revoke_auth(self, value: str, *, now_ms: int) -> bool:
        return self._auth_sessions.revoke(self.hash_token(value), now_ms=now_ms)

    def revoke_user_auth(self, user_id: int, *, now_ms: int) -> int:
        return self._auth_sessions.revoke_user(user_id, now_ms=now_ms)

    def issue_game(
        self,
        *,
        game_id: str,
        user_id: int,
        role: str,
        color: str | None,
        now_ms: int,
    ) -> IssuedToken:
        value = secrets.token_urlsafe(self._token_bytes)
        self._game_tokens.create(
            game_id=game_id,
            user_id=user_id,
            token_hash=self.hash_token(value),
            role=role,
            color=color,
            now_ms=now_ms,
        )
        return IssuedToken(value, None)

    def verify_game(self, value: str, *, game_id: str, now_ms: int):
        return self._game_tokens.find_valid(
            self.hash_token(value), game_id=game_id, now_ms=now_ms
        )

    def begin_game_grace(self, value: str, *, grace_expires_at_ms: int) -> bool:
        return self._game_tokens.begin_grace(
            self.hash_token(value), grace_expires_at_ms=grace_expires_at_ms
        )

    def restore_game(self, value: str, *, now_ms: int) -> bool:
        return self._game_tokens.restore_active(
            self.hash_token(value), now_ms=now_ms
        )

    def revoke_game(self, value: str, *, now_ms: int) -> bool:
        return self._game_tokens.revoke(self.hash_token(value), now_ms=now_ms)

    def revoke_game_tokens(self, game_id: str, *, now_ms: int) -> int:
        return self._game_tokens.revoke_game(game_id, now_ms=now_ms)

    def revoke_user_game_tokens(
        self, game_id: str, user_id: int, *, now_ms: int
    ) -> int:
        return self._game_tokens.revoke_game_user(
            game_id, user_id, now_ms=now_ms
        )

    @staticmethod
    def hash_token(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
