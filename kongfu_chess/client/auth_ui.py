"""Presentation-neutral contracts for an in-window authentication flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class AuthAction(str, Enum):
    LOGIN = "login"
    REGISTER = "register"


class AuthUiMode(str, Enum):
    OPENCV = "opencv"
    CLI_DEBUG = "cli_debug"


@dataclass(frozen=True)
class AuthUiConfig:
    mode: AuthUiMode = AuthUiMode.OPENCV
    cli_debug_enabled: bool = False

    def __post_init__(self) -> None:
        if self.mode is AuthUiMode.CLI_DEBUG and not self.cli_debug_enabled:
            raise ValueError("CLI authentication requires explicit debug enablement")


@dataclass(frozen=True)
class AuthSubmission:
    action: AuthAction
    username: str
    password: str
    email: str | None = None
    phone: str | None = None


class AuthInputProvider(Protocol):
    """Supply user intent without choosing OpenCV, terminal, or another toolkit."""

    def poll_submission(self) -> AuthSubmission | None: ...


class AuthScreen(Protocol):
    """Render authentication state inside the active client presentation."""

    def show_login(self) -> None: ...

    def show_registration(self) -> None: ...

    def show_error(self, localized_message: str) -> None: ...

    def clear_sensitive_fields(self) -> None: ...
