import threading
import time
from queue import Queue
from types import SimpleNamespace

from kongfu_chess.client import (
    ClientLocalizer,
    ClientMessageFactory,
    ClientNetworkWorker,
    ClientSessionState,
    ClientUiState,
    OpenCvClientRenderer,
    TransportResult,
    UiAction,
    UiHit,
    WebSocketClientTransport,
)
from kongfu_chess.client.client_application import (
    OpenCvClientApplication,
    build_opencv_client,
)
from kongfu_chess.protocol import EnvelopePolicy, MessageEnvelope


POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


def envelope(request_id="request-1"):
    return MessageEnvelope.from_mapping(
        {
            "protocol_version": "1.0",
            "type": "login_request",
            "request_id": request_id,
            "timestamp_ms": 1000,
            "payload": {"username": "Dana", "password": "secret7"},
        },
        POLICY,
    )


class FakeTransport:
    def __init__(self, *, fails=False):
        self.fails = fails
        self.closed = False
        self.called = threading.Event()
        self._incoming = Queue()

    def send(self, request):
        self.called.set()
        if self.fails:
            raise OSError("secret details must not escape")
        self._incoming.put(request)

    def receive(self, *, timeout=None):
        if timeout is None:
            return self._incoming.get()
        return self._incoming.get(timeout=timeout)

    def request(self, request):
        self.send(request)
        return self.receive()

    def close(self):
        self.closed = True


def wait_for_result(worker):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        results = worker.poll()
        if results:
            return results[0]
        time.sleep(0.005)
    raise AssertionError("network worker did not produce a result")


def test_network_worker_returns_responses_and_redacted_error_codes():
    transport = FakeTransport()
    worker = ClientNetworkWorker(transport)
    worker.start()
    worker.start()
    worker.submit(envelope())
    result = wait_for_result(worker)
    assert result.envelope.request_id == "request-1"
    assert worker.poll() == ()
    worker.close()
    assert transport.closed is True

    failing = FakeTransport(fails=True)
    worker = ClientNetworkWorker(failing)
    worker.submit(envelope("request-2"))
    result = wait_for_result(worker)
    assert result == TransportResult("request-2", error_code="network_error")
    assert "secret details" not in repr(result)
    worker.close()


def test_network_worker_can_close_before_start():
    transport = FakeTransport()
    ClientNetworkWorker(transport).close()
    assert transport.closed is True


class FakeSocket:
    def __init__(self, response, *, fails=False):
        self.response = response
        self.fails = fails
        self.sent = []
        self.closed = False

    def send(self, raw):
        self.sent.append(raw)
        if self.fails:
            raise OSError("closed")

    def recv(self):
        return self.response

    def close(self):
        self.closed = True


def test_websocket_transport_reuses_socket_closes_and_resets_on_failure(monkeypatch):
    request = envelope()
    socket = FakeSocket(request.to_json())
    calls = []
    monkeypatch.setattr(
        "kongfu_chess.client.transport.connect",
        lambda uri, max_size: calls.append((uri, max_size)) or socket,
    )
    transport = WebSocketClientTransport("ws://localhost:8765", POLICY)
    assert transport.request(request) == request
    assert transport.request(request) == request
    assert len(calls) == 1
    transport.close()
    transport.close()
    assert socket.closed is True

    broken = FakeSocket(request.to_json(), fails=True)
    monkeypatch.setattr(
        "kongfu_chess.client.transport.connect",
        lambda _uri, max_size: broken,
    )
    transport = WebSocketClientTransport("ws://localhost:8765", POLICY)
    try:
        transport.request(request)
    except OSError:
        pass
    else:
        raise AssertionError("transport failure should propagate to worker")
    assert broken.closed is True


class FakeController:
    def __init__(self):
        self.state = ClientUiState()
        self.session = ClientSessionState()
        self.keys = []
        self.actions = []
        self.fields = []
        self.responses = []
        self.failures = []
        self.ticks = []
        self.board_cells = []

    def handle_key(self, key):
        self.keys.append(key)

    def handle_action(self, action):
        self.actions.append(action)

    def activate_field(self, field):
        self.fields.append(field)

    def handle_response(self, response):
        self.responses.append(response)

    def handle_transport_failure(self, request_id, code):
        self.failures.append((request_id, code))

    def disconnect_active_game(self):
        return None

    def handle_push(self, envelope):
        return None

    def tick(self, now_ms):
        self.ticks.append(now_ms)

    def handle_board_cell(self, row, col):
        self.board_cells.append((row, col))


class FakeNetwork:
    def __init__(self, results=()):
        self.results = tuple(results)
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def poll(self):
        results, self.results = self.results, ()
        return results

    def close(self):
        self.closed = True


class FakeRenderer:
    def __init__(self, hit):
        self.hit = hit
        self.rendered = []

    def hit_test(self, _x, _y):
        return self.hit

    def render(self, state, session):
        self.rendered.append((state, session))
        return None


def test_opencv_application_step_routes_network_clicks_and_frames(monkeypatch):
    request = envelope()
    controller = FakeController()
    network = FakeNetwork(
        (
            TransportResult(request.request_id, envelope=request),
            TransportResult("request-2", error_code="network_error"),
        )
    )
    renderer = FakeRenderer(UiHit("field", "username"))
    app = OpenCvClientApplication(
        controller, renderer, network, clock_ms=lambda: 1234
    )
    app._clicks.register_click(10, 20)
    monkeypatch.setattr(
        "kongfu_chess.client.client_application.cv2.imshow", lambda *_: None
    )
    app.step()
    assert controller.responses == [request]
    assert controller.failures == [("request-2", "network_error")]
    assert controller.fields == ["username"]
    assert controller.ticks == [1234]
    assert len(renderer.rendered) == 1

    renderer.hit = UiHit("action", UiAction.PLAY)
    app._clicks.register_click(10, 20)
    app.step()
    assert controller.actions == [UiAction.PLAY]

    renderer.hit = UiHit("board_cell", (6, 4))
    app._clicks.register_click(10, 20)
    app.step()
    assert controller.board_cells == [(6, 4)]


def test_opencv_application_run_uses_only_opencv_event_loop(monkeypatch):
    controller = FakeController()
    network = FakeNetwork()
    renderer = FakeRenderer(None)
    app = OpenCvClientApplication(controller, renderer, network)
    keys = iter((65, 27))
    callbacks = []
    monkeypatch.setattr(
        "kongfu_chess.client.client_application.cv2.namedWindow", lambda *_: None
    )
    monkeypatch.setattr(
        "kongfu_chess.client.client_application.cv2.setMouseCallback",
        lambda *args: callbacks.append(args),
    )
    monkeypatch.setattr(
        "kongfu_chess.client.client_application.cv2.imshow", lambda *_: None
    )
    monkeypatch.setattr(
        "kongfu_chess.client.client_application.cv2.waitKeyEx",
        lambda _delay: next(keys),
    )
    monkeypatch.setattr(
        "kongfu_chess.client.client_application.cv2.destroyWindow", lambda *_: None
    )

    app.run()

    assert network.started is True and network.closed is True
    assert controller.keys == [65]
    assert callbacks


def test_build_opencv_client_uses_portable_config_and_locales(tmp_path):
    config = SimpleNamespace(
        network=SimpleNamespace(
            host="127.0.0.1",
            port=8765,
            protocol_version="1.0",
            max_message_bytes=4096,
            request_id_max_length=64,
            message_type_max_length=64,
        ),
        security=SimpleNamespace(
            username_min_length=3,
            username_max_length=20,
            password_min_length=6,
        ),
    )
    locale = tmp_path / "en.json"
    locale.write_text('{"invalid_credentials":"Try again"}', encoding="utf-8")

    app = build_opencv_client(config, locale_directory=tmp_path)

    assert isinstance(app._renderer, OpenCvClientRenderer)
    app._network.close()
