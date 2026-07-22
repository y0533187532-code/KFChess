"""Application-message routing without transport or engine knowledge."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ...protocol import MessageEnvelope, ProtocolError, ProtocolErrorCode


@dataclass(frozen=True)
class RequestContext:
    connection_id: str
    envelope: MessageEnvelope


@dataclass(frozen=True)
class OutgoingMessage:
    type: str
    payload: Mapping[str, Any]


class MessageRouter:
    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register(self, message_type: str, handler: Callable) -> None:
        if message_type in self._handlers:
            raise ValueError(f"Handler already registered for {message_type}")
        self._handlers[message_type] = handler

    async def route(self, context: RequestContext) -> OutgoingMessage:
        handler = self._handlers.get(context.envelope.type)
        if handler is None:
            raise ProtocolError(
                ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE,
                "No application handler is registered for this message type",
            )
        result = handler(context)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, OutgoingMessage):
            raise TypeError("Message handlers must return OutgoingMessage")
        return OutgoingMessage(result.type, MappingProxyType(dict(result.payload)))
