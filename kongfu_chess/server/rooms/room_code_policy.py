"""Room-code normalization, validation, and ambiguity-free generation."""

from __future__ import annotations

import re
import secrets
from typing import Callable

from ...protocol import ProtocolErrorCode
from .room_models import RoomsError


class RoomCodePolicy:
    CODE_LENGTH = 6
    GENERATION_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    CODE_ALPHABET = GENERATION_ALPHABET
    CONFUSING_CHARACTERS = frozenset("O0I1")
    _CODE_PATTERN = re.compile(r"^[A-Z0-9]{6}$")

    def __init__(self, generator: Callable[[], str] | None = None):
        self._generator = generator or self._random_code

    @classmethod
    def normalize(cls, code: str) -> str:
        if not isinstance(code, str):
            raise RoomsError(ProtocolErrorCode.INVALID_ROOM_CODE)
        return cls.validate(code.upper())

    @classmethod
    def validate(cls, code: str) -> str:
        if not cls.is_valid(code):
            raise RoomsError(ProtocolErrorCode.INVALID_ROOM_CODE)
        return code

    @classmethod
    def is_valid(cls, code: str) -> bool:
        return isinstance(code, str) and cls._CODE_PATTERN.fullmatch(code) is not None

    def generate(self) -> str:
        code = self.normalize(self._generator())
        if any(character in self.CONFUSING_CHARACTERS for character in code):
            raise ValueError("Generated room codes must exclude O, 0, I, and 1")
        return code

    @classmethod
    def _random_code(cls) -> str:
        return "".join(
            secrets.choice(cls.GENERATION_ALPHABET) for _ in range(cls.CODE_LENGTH)
        )
