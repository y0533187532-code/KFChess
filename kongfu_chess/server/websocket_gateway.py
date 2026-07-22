"""WebSocket adapter for the transport-neutral envelope and router."""

from __future__ import annotations

import time
import uuid

from websockets.asyncio.server import serve

from ..protocol import MessageEnvelope, ProtocolError, ProtocolErrorCode
from .routing import MessageRouter, OutgoingMessage, RequestContext


class WebSocketGateway:
    def __init__(
        self,
        registry,
        router: MessageRouter,
        policy,
        *,
        game_connections=None,
        logger=None,
        on_connection_closed=None,
    ):
        self._registry = registry
        self._router = router
        self._policy = policy
        self._game_connections = game_connections
        self._logger = logger
        self._on_connection_closed = on_connection_closed
        self._server = None

    async def handle(self, websocket) -> None:
        connection_id = uuid.uuid4().hex
        if not await self._registry.try_add(connection_id, websocket):
            self._log(
                "connection_rejected",
                connection_id=connection_id,
                reason="connection_limit_reached",
            )
            await websocket.close(
                1013,
                "connection limit reached",
            )
            return
        self._log("connection_opened", connection_id=connection_id)
        try:
            async for raw in websocket:
                await websocket.send(await self._response(raw, connection_id))
        finally:
            binding = None
            if self._game_connections is not None:
                binding = self._game_connections.pop_connection(connection_id)
            await self._registry.remove(connection_id)
            if binding is not None and self._on_connection_closed is not None:
                await self._on_connection_closed(binding)
            self._log("connection_closed", connection_id=connection_id)

    async def start(self, host: str, port: int):
        if self._server is not None:
            return self._server
        self._server = await serve(
            self.handle,
            host,
            port,
            max_size=self._policy.max_message_bytes,
        )
        return self._server

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def push(self, connection_id: str, outgoing: OutgoingMessage) -> None:
        websocket = await self._registry.get(connection_id)
        if websocket is None:
            return
        envelope = self._make_envelope(
            outgoing.type,
            uuid.uuid4().hex,
            dict(outgoing.payload),
        )
        try:
            await websocket.send(envelope.to_json())
        except Exception:
            await self._registry.remove(connection_id)
            if self._game_connections is not None:
                self._game_connections.remove_connection(connection_id)

    async def broadcast(
        self, game_id: str, outgoing: OutgoingMessage, *, exclude=()
    ) -> None:
        if self._game_connections is None:
            return
        excluded = frozenset(exclude)
        for connection_id in self._game_connections.connections_for(game_id):
            if connection_id in excluded:
                continue
            await self.push(connection_id, outgoing)

    async def _response(self, raw, connection_id: str) -> str:
        request_id = self._best_effort_request_id(raw)
        try:
            envelope = MessageEnvelope.from_json(raw, self._policy)
            request_id = envelope.request_id
            outgoing = await self._router.route(
                RequestContext(connection_id, envelope)
            )
            return self._make_envelope(
                outgoing.type, request_id, dict(outgoing.payload)
            ).to_json()
        except ProtocolError as exc:
            self._log(
                "message_rejected",
                connection_id=connection_id,
                request_id=request_id,
                code=exc.code.value,
            )
            return self._make_envelope(
                "error", request_id, {"code": exc.code.value}
            ).to_json()
        except Exception:
            self._log(
                "handler_failed",
                connection_id=connection_id,
                request_id=request_id,
                code=ProtocolErrorCode.INTERNAL_ERROR.value,
            )
            return self._make_envelope(
                "error",
                request_id,
                {"code": ProtocolErrorCode.INTERNAL_ERROR.value},
            ).to_json()

    def _make_envelope(self, message_type, request_id, payload):
        return MessageEnvelope.from_mapping(
            {
                "protocol_version": self._policy.protocol_version,
                "type": message_type,
                "request_id": request_id,
                "timestamp_ms": time.time_ns() // 1_000_000,
                "payload": payload,
            },
            self._policy,
        )

    @staticmethod
    def _best_effort_request_id(raw) -> str:
        import json

        try:
            value = json.loads(raw)
            request_id = value.get("request_id")
            if isinstance(request_id, str) and request_id:
                return request_id
        except (TypeError, ValueError):
            pass
        return uuid.uuid4().hex

    def _log(self, event, **values):
        if self._logger is not None:
            self._logger.info(event, extra={"event": event, **values})
