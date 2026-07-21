"""Portable WebSocket transport and non-blocking UI request dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Protocol

from websockets.sync.client import connect

from ..protocol import MessageEnvelope


class ClientTransport(Protocol):
    def request(self, envelope: MessageEnvelope) -> MessageEnvelope: ...

    def close(self) -> None: ...


class WebSocketClientTransport:
    """Persistent synchronous socket used only from the network worker thread."""

    def __init__(self, uri: str, policy):
        self._uri = uri
        self._policy = policy
        self._socket = None
        self._lock = Lock()

    def request(self, envelope: MessageEnvelope) -> MessageEnvelope:
        with self._lock:
            if self._socket is None:
                self._socket = connect(
                    self._uri, max_size=self._policy.max_message_bytes
                )
            try:
                self._socket.send(envelope.to_json())
                raw = self._socket.recv()
                return MessageEnvelope.from_json(raw, self._policy)
            except Exception:
                self._socket.close()
                self._socket = None
                raise

    def close(self) -> None:
        with self._lock:
            if self._socket is not None:
                self._socket.close()
                self._socket = None


@dataclass(frozen=True)
class TransportResult:
    request_id: str
    envelope: MessageEnvelope | None = None
    error_code: str | None = None


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
                    response = self._transport.request(envelope)
                except Exception:
                    self._results.put(
                        TransportResult(
                            request_id=envelope.request_id,
                            error_code="network_error",
                        )
                    )
                else:
                    self._results.put(
                        TransportResult(
                            request_id=envelope.request_id,
                            envelope=response,
                        )
                    )
        finally:
            self._transport.close()
