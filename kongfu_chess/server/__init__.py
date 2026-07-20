"""Authoritative server application components."""

from .game_session import (
    CommandResult,
    GameSession,
    HandlerResult,
    SessionClosedError,
    SessionCommand,
    SessionCommandType,
)
from .connections import ConnectionRegistry
from .auth_service import (
    AuthError,
    AuthPrincipal,
    AuthService,
    AuthenticatedSession,
    RegisteredAccount,
    build_auth_service,
)
from .password_hasher import PasswordHasher
from .auth_handlers import AuthHandlers
from .routing import MessageRouter, OutgoingMessage, RequestContext
from .websocket_gateway import WebSocketGateway

__all__ = [
    "CommandResult",
    "ConnectionRegistry",
    "AuthError",
    "AuthHandlers",
    "AuthPrincipal",
    "AuthService",
    "AuthenticatedSession",
    "GameSession",
    "HandlerResult",
    "MessageRouter",
    "OutgoingMessage",
    "PasswordHasher",
    "RequestContext",
    "RegisteredAccount",
    "build_auth_service",
    "SessionClosedError",
    "SessionCommand",
    "SessionCommandType",
    "WebSocketGateway",
]
