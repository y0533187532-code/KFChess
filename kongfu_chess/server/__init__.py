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
from .routing import MessageRouter, OutgoingMessage, RequestContext
from .websocket_gateway import WebSocketGateway

__all__ = [
    "CommandResult",
    "ConnectionRegistry",
    "GameSession",
    "HandlerResult",
    "MessageRouter",
    "OutgoingMessage",
    "RequestContext",
    "SessionClosedError",
    "SessionCommand",
    "SessionCommandType",
    "WebSocketGateway",
]
