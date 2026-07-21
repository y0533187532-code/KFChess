import asyncio

from kongfu_chess.client import WebSocketClientTransport
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope
from kongfu_chess.server import (
    ConnectionRegistry,
    MessageRouter,
    OutgoingMessage,
    WebSocketGateway,
)


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


def test_client_transport_exchanges_shared_envelopes_with_server_gateway():
    async def scenario():
        router = MessageRouter()
        router.register(
            "login_request",
            lambda context: OutgoingMessage(
                "command_result",
                {"accepted": True, "username": context.envelope.payload["username"]},
            ),
        )
        gateway = WebSocketGateway(ConnectionRegistry(), router, POLICY)
        server = await gateway.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        transport = WebSocketClientTransport(f"ws://127.0.0.1:{port}", POLICY)
        request = MessageEnvelope.from_mapping(
            {
                "protocol_version": "1.0",
                "type": "login_request",
                "request_id": "client-request-1",
                "timestamp_ms": 1000,
                "payload": {"username": "Dana", "password": "secret7"},
            },
            POLICY,
        )
        try:
            return await asyncio.to_thread(transport.request, request)
        finally:
            await asyncio.to_thread(transport.close)
            await gateway.stop()

    response = asyncio.run(scenario())

    assert response.request_id == "client-request-1"
    assert response.type == "command_result"
    assert response.payload["accepted"] is True
    assert response.payload["username"] == "Dana"
