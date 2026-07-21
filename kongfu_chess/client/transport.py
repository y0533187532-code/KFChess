"""Portable WebSocket transport and non-blocking UI request dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Literal, Protocol

from websockets.sync.client import connect

from ..protocol import MessageEnvelope, MessageType


SERVER_PUSH_MESSAGE_TYPES = frozenset(
    {
        MessageType.STATE_UPDATE.value,
        MessageType.DISCONNECT_COUNTDOWN.value,
        MessageType.GAME_CANCELLED.value,
        MessageType.GAME_FORFEIT.value,
        MessageType.GAME_LIFECYCLE_STATUS.value,
        MessageType.GAME_OVER.value,
    }
)


class ClientTransport(Protocol):
    def send(self, envelope: MessageEnvelope) -> None: ...

    def receive(self, *, timeout: float | None = None) -> MessageEnvelope: ...

    def close(self) -> None: ...


class WebSocketClientTransport:
    """Persistent synchronous socket with a background reader for server push."""

    def __init__(self, uri: str, policy):
        self._uri = uri
        self._policy = policy
        self._socket = None
        self._lock = Lock()
        self._incoming: Queue[MessageEnvelope] = Queue()
        self._reader: Thread | None = None
        self._closed = False

    def send(self, envelope: MessageEnvelope) -> None:
        self._ensure_connected()
        with self._lock:
            if self._socket is None:
                raise OSError("WebSocket connection is not available")
            try:
                self._socket.send(envelope.to_json())
            except Exception:
                self._socket.close()
                self._socket = None
                raise

    def receive(self, *, timeout: float | None = None) -> MessageEnvelope:
        if timeout is None:
            return self._incoming.get()
        return self._incoming.get(timeout=timeout)

    def request(self, envelope: MessageEnvelope) -> MessageEnvelope:
        """Send one request and wait for its matching response envelope."""

        self.send(envelope)
        while True:
            response = self.receive()
            if response.request_id == envelope.request_id:
                return response
            if response.type in SERVER_PUSH_MESSAGE_TYPES:
                self._incoming.put(response)
                continue

    def close(self) -> None:
        self._closed = True
        with self._lock:
            if self._socket is not None:
                self._socket.close()
                self._socket = None

    def _ensure_connected(self) -> None:
        if self._socket is not None:
            return
        self._socket = connect(
            self._uri, max_size=self._policy.max_message_bytes
        )
        self._reader = Thread(
            target=self._read_loop,
            name="kfchess-ws-reader",
            daemon=True,
        )
        self._reader.start()

    def _read_loop(self) -> None:
        while not self._closed:
            try:
                with self._lock:
                    socket = self._socket
                if socket is None:
                    return
                raw = socket.recv()
            except Exception:
                with self._lock:
                    if self._socket is not None:
                        self._socket.close()
                    self._socket = None
                return
            self._incoming.put(MessageEnvelope.from_json(raw, self._policy))


@dataclass(frozen=True)
class TransportResult:
    request_id: str | None
    envelope: MessageEnvelope | None = None
    error_code: str | None = None
    kind: Literal["response", "push"] = "response"


class ClientNetworkWorker:
    """Keep socket waits off the OpenCV event/render loop."""

    def __init__(self, transport: ClientTransport):
        self._transport = transport
        self._requests: Queue = Queue()
        self._results: Queue[TransportResult] = Queue()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run, name="kfchess-network", daemon=True)
        self._thread.start()

    def submit(self, envelope: MessageEnvelope) -> None:
        self.start()
        self._requests.put(envelope)

    def send_immediate(self, envelope: MessageEnvelope) -> None:
        self._transport.send(envelope)

    def poll(self) -> tuple[TransportResult, ...]:
        results = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except Empty:
                return tuple(results)

    def close(self) -> None:
        thread = self._thread
        if thread is None:
            self._transport.close()
            return
        self._requests.put(None)
        thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        try:
            while True:
                envelope = self._requests.get()
                if envelope is None:
                    return
                try:
                    self._transport.send(envelope)
                    while True:
                        response = self._transport.receive()
                        if response.request_id == envelope.request_id:
                            self._results.put(
                                TransportResult(
                                    request_id=envelope.request_id,
                                    envelope=response,
                                    kind="response",
                                )
                            )
                            break
                        if response.type in SERVER_PUSH_MESSAGE_TYPES:
                            self._results.put(
                                TransportResult(
                                    request_id=None,
                                    envelope=response,
                                    kind="push",
                                )
                            )
                            continue
                except Exception:
                    self._results.put(
                        TransportResult(
                            request_id=envelope.request_id,
                            error_code="network_error",
                        )
                    )
        finally:
            self._transport.close()
