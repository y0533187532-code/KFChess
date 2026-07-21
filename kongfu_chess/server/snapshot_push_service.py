"""Broadcast authoritative STATE_UPDATE messages after sequence changes."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from ..protocol import MessageEnvelope, MessageType
from .routing import OutgoingMessage


class SnapshotPushService:
    def __init__(self, gateway, game_connections, policy, *, clock_ms):
        self._gateway = gateway
        self._game_connections = game_connections
        self._policy = policy
        self._clock_ms = clock_ms

    def bind(self, connection_id: str, game_id: str, user_id: int) -> None:
        self._game_connections.bind(connection_id, game_id, user_id)

    async def notify(
        self,
        game_id: str,
        sequence: int,
        payload: Mapping[str, Any],
    ) -> None:
        snapshot = payload.get("snapshot")
        if snapshot is None:
            return
        message = OutgoingMessage(
            MessageType.STATE_UPDATE.value,
            {
                "game_id": game_id,
                "sequence": sequence,
                "snapshot": dict(snapshot),
            },
        )
        await self._gateway.broadcast(game_id, message)

    def make_envelope(self, outgoing: OutgoingMessage) -> MessageEnvelope:
        return MessageEnvelope.from_mapping(
            {
                "protocol_version": self._policy.protocol_version,
                "type": outgoing.type,
                "request_id": uuid.uuid4().hex,
                "timestamp_ms": self._clock_ms(),
                "payload": dict(outgoing.payload),
            },
            self._policy,
        )
