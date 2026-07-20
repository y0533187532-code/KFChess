"""Strict, transport-neutral codec for the shared JSON message envelope."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .error_codes import ProtocolErrorCode
from .message_types import SUPPORTED_MESSAGE_TYPES


_MESSAGE_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_ENVELOPE_FIELDS = frozenset(
    {"protocol_version", "type", "request_id", "timestamp_ms", "payload"}
)


class ProtocolError(ValueError):
    def __init__(self, code: ProtocolErrorCode, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class EnvelopePolicy:
    protocol_version: str
    max_message_bytes: int
    request_id_max_length: int
    message_type_max_length: int
    supported_types: frozenset[str] = SUPPORTED_MESSAGE_TYPES


@dataclass(frozen=True)
class MessageEnvelope:
    protocol_version: str
    type: str
    request_id: str
    timestamp_ms: int
    payload: Mapping[str, Any]

    @classmethod
    def from_json(cls, raw: str | bytes, policy: EnvelopePolicy) -> "MessageEnvelope":
        encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
        if len(encoded) > policy.max_message_bytes:
            raise ProtocolError(
                ProtocolErrorCode.MESSAGE_TOO_LARGE,
                "Encoded message exceeds configured size limit",
            )
        try:
            document = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError(ProtocolErrorCode.INVALID_JSON, "Invalid JSON") from exc
        return cls.from_mapping(document, policy)

    @classmethod
    def from_mapping(
        cls, document: Any, policy: EnvelopePolicy
    ) -> "MessageEnvelope":
        if not isinstance(document, dict):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_ENVELOPE,
                "Envelope must be a JSON object",
            )
        missing = _ENVELOPE_FIELDS.difference(document)
        if missing:
            raise ProtocolError(
                ProtocolErrorCode.MISSING_FIELD,
                f"Missing envelope field: {sorted(missing)[0]}",
            )
        extra = set(document).difference(_ENVELOPE_FIELDS)
        if extra:
            raise ProtocolError(
                ProtocolErrorCode.INVALID_ENVELOPE,
                f"Unexpected envelope field: {sorted(extra)[0]}",
            )

        version = cls._non_empty_string(document["protocol_version"], "protocol_version")
        if version != policy.protocol_version:
            raise ProtocolError(
                ProtocolErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
                "Unsupported protocol version",
            )
        message_type = cls._non_empty_string(document["type"], "type")
        if (
            len(message_type) > policy.message_type_max_length
            or _MESSAGE_TYPE_PATTERN.fullmatch(message_type) is None
        ):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "Invalid message type",
            )
        if message_type not in policy.supported_types:
            raise ProtocolError(
                ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE,
                "Unknown message type",
            )

        request_id = cls._non_empty_string(document["request_id"], "request_id")
        if len(request_id) > policy.request_id_max_length:
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "request_id exceeds configured length limit",
            )
        timestamp_ms = document["timestamp_ms"]
        if (
            isinstance(timestamp_ms, bool)
            or not isinstance(timestamp_ms, int)
            or timestamp_ms < 0
        ):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "timestamp_ms must be a non-negative integer",
            )
        payload = document["payload"]
        if not isinstance(payload, dict):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "payload must be an object",
            )
        return cls(
            protocol_version=version,
            type=message_type,
            request_id=request_id,
            timestamp_ms=timestamp_ms,
            payload=_freeze(payload),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "type": self.type,
            "request_id": self.request_id,
            "timestamp_ms": self.timestamp_ms,
            "payload": _thaw(self.payload),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_mapping(), ensure_ascii=False, separators=(",", ":")
        )

    @staticmethod
    def _non_empty_string(value: Any, name: str) -> str:
        if not isinstance(value, str) or not value:
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                f"{name} must be a non-empty string",
            )
        return value


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ProtocolError(
        ProtocolErrorCode.INVALID_FIELD,
        "payload contains a value unsupported by JSON",
    )


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
