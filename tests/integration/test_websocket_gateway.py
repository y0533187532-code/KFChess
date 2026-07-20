import asyncio
import json

from websockets.asyncio.client import connect

from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope
from kongfu_chess.server import (
    ConnectionRegistry,
    MessageRouter,
    OutgoingMessage,
    WebSocketGateway,
)


POLICY = EnvelopePolicy("1.0", 4096, 64, 32)


def run(coro):
    return asyncio.run(coro)


def request(request_id="request-1"):
    return MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": "login_request",
            "request_id": request_id,
            "timestamp_ms": 1000,
            "payload": {"username": "Dana"},
        },
        POLICY,
    ).to_json()


def test_gateway_routes_two_real_websocket_clients_and_cleans_registry():
    async def scenario():
        calls = []

        async def login(context):
            calls.append((context.connection_id, context.envelope.request_id))
            return OutgoingMessage("command_result", {"code": "ok"})

        registry = ConnectionRegistry()
        router = MessageRouter()
        router.register("login_request", login)
        gateway = WebSocketGateway(registry, router, POLICY)
        server = await gateway.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            async with connect(f"ws://127.0.0.1:{port}") as first, connect(
                f"ws://127.0.0.1:{port}"
            ) as second:
                await asyncio.gather(
                    first.send(request("request-1")),
                    second.send(request("request-2")),
                )
                responses = await asyncio.gather(first.recv(), second.recv())
                live_count = len(await registry.connection_ids())
            await asyncio.sleep(0)
            remaining = await registry.connection_ids()
        finally:
            await gateway.stop()
        return calls, responses, live_count, remaining

    calls, responses, live_count, remaining = run(scenario())

    assert live_count == 2
    assert remaining == ()
    assert len(calls) == 2
    decoded = [json.loads(value) for value in responses]
    assert {item["request_id"] for item in decoded} == {"request-1", "request-2"}
    assert all(item["payload"]["code"] == "ok" for item in decoded)


def test_gateway_returns_stable_error_for_invalid_json_and_unregistered_route():
    async def scenario():
        gateway = WebSocketGateway(ConnectionRegistry(), MessageRouter(), POLICY)
        server = await gateway.start("127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            async with connect(f"ws://127.0.0.1:{port}") as client:
                await client.send("{")
                invalid = json.loads(await client.recv())
                await client.send(request("request-2"))
                unknown = json.loads(await client.recv())
        finally:
            await gateway.stop()
        return invalid, unknown

    invalid, unknown = run(scenario())

    assert invalid["payload"]["code"] == "invalid_json"
    assert unknown["request_id"] == "request-2"
    assert unknown["payload"]["code"] == "unknown_message_type"
