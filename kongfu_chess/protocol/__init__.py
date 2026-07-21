"""Versioned JSON contracts shared by transports, clients, and servers."""

from .envelope import EnvelopePolicy, MessageEnvelope, ProtocolError
from .error_codes import ProtocolErrorCode
from .game_snapshot import (
    GameSnapshotPayloadError,
    deserialize_game_snapshot,
    serialize_game_snapshot,
)
from .localization import LocalizationCatalog, LocalizationError
from .message_types import MessageType, SUPPORTED_MESSAGE_TYPES

__all__ = [
    "EnvelopePolicy",
    "GameSnapshotPayloadError",
    "LocalizationCatalog",
    "LocalizationError",
    "MessageEnvelope",
    "MessageType",
    "ProtocolError",
    "ProtocolErrorCode",
    "SUPPORTED_MESSAGE_TYPES",
    "deserialize_game_snapshot",
    "serialize_game_snapshot",
]
