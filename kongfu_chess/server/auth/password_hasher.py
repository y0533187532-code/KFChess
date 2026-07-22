"""Versioned scrypt password hashing independent of account persistence."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


class PasswordHasher:
    _SCHEME = "scrypt"
    _VERSION = "1"

    def __init__(
        self,
        *,
        salt_bytes: int,
        n: int,
        r: int,
        p: int,
        hash_bytes: int,
    ):
        self._salt_bytes = salt_bytes
        self._n = n
        self._r = r
        self._p = p
        self._hash_bytes = hash_bytes

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(self._salt_bytes)
        digest = self._derive(
            password,
            salt=salt,
            n=self._n,
            r=self._r,
            p=self._p,
            hash_bytes=self._hash_bytes,
        )
        return "$".join(
            (
                self._SCHEME,
                self._VERSION,
                str(self._n),
                str(self._r),
                str(self._p),
                str(self._hash_bytes),
                self._encode(salt),
                self._encode(digest),
            )
        )

    def verify(self, password: str, encoded_hash: str) -> bool:
        try:
            scheme, version, n, r, p, hash_bytes, salt, expected = encoded_hash.split(
                "$"
            )
            if scheme != self._SCHEME or version != self._VERSION:
                return False
            derived = self._derive(
                password,
                salt=self._decode(salt),
                n=int(n),
                r=int(r),
                p=int(p),
                hash_bytes=int(hash_bytes),
            )
            expected_bytes = self._decode(expected)
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(derived, expected_bytes)

    @staticmethod
    def _derive(password, *, salt, n, r, p, hash_bytes):
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=hash_bytes,
        )

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)
