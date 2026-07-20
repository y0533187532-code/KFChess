"""Versioned JSON contracts independent of WebSocket and game-engine APIs."""

from .envelope import EnvelopePolicy, MessageEnvelope, ProtocolError
from .error_codes import ProtocolErrorCode
from .localization import LocalizationCatalog, LocalizationError
from .message_types import MessageType, SUPPORTED_MESSAGE_TYPES

__all__ = [
    "EnvelopePolicy",
    "LocalizationCatalog",
    "LocalizationError",
    "MessageEnvelope",
    "MessageType",
    "ProtocolError",
    "ProtocolErrorCode",
    "SUPPORTED_MESSAGE_TYPES",
]
