
"""Production OpenCV client shell for auth, menu, Play, and Room entry."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import cv2

from ..graphics.game_window import GAME_WINDOW_NAME, MouseClickBuffer, on_mouse_event
from ..infrastructure import ConfigProvider
from ..infrastructure.structured_logging import configure_json_logger
from ..protocol import EnvelopePolicy, LocalizationCatalog
from .client_logger import ClientEventLogger
from .controller import ClientController
from .localization import ClientLocalizer
from .messages import ClientMessageFactory
from .screen_renderer import OpenCvClientRenderer
from .session import ClientSessionState
from .transport import ClientNetworkWorker, WebSocketClientTransport
from .ui_state import ClientScreen, ClientUiConstraints, UiAction


def _configure_client_logger(config) -> logging.Logger:
    return configure_json_logger(
        "kfchess.client",
        config.logging.client_path,
        level=config.logging.level,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        retention_days=config.logging.retention_days,
    )


class OpenCvClientApplication:
    def __init__(
        self,
        controller,
        renderer,
        network_worker,
        *,
        window_name: str = GAME_WINDOW_NAME,
        clock_ms=None,
    ):
        self._controller = controller
        self._renderer = renderer
        self._network = network_worker
        self._window_name = window_name
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._clicks = MouseClickBuffer()

    def run(self) -> None:
        cv2.namedWindow(self._window_name)
        cv2.setMouseCallback(self._window_name, on_mouse_event, self._clicks)
        self._network.start()
        try:
            while True:
                self.step()
                key_code = cv2.waitKeyEx(16)
                if key_code >= 0 and key_code & 0xFF == 27:
                    if self._controller.state.screen is ClientScreen.GAME_BOARD:
                        if self._controller.state.game_leave_confirm_pending:
                            self._controller.handle_action(UiAction.GAME_LEAVE_CANCEL)
                        else:
                            self._controller.handle_action(UiAction.GAME_LEAVE)
                    else:
                        self._controller.leave_active_room()
                        self._controller.disconnect_active_game()
                        return
                self._controller.handle_key(key_code)
        finally:
            self._network.close()
            cv2.destroyWindow(self._window_name)

    def step(self) -> None:
        for result in self._network.poll():
            if result.kind == "push" and result.envelope is not None:
                self._controller.handle_push(result.envelope)
                continue
            if result.envelope is not None:
                self._controller.handle_response(result.envelope)
            else:
                self._controller.handle_transport_failure(
                    result.request_id, result.error_code or "network_error"
                )
        now_ms = self._clock_ms()
        self._controller.tick(now_ms)
        pending_click = self._clicks.pop_click()
        if pending_click is not None:
            hit = self._renderer.hit_test(*pending_click)
            if hit is not None:
                if hit.kind == "field":
                    self._controller.activate_field(str(hit.value))
                elif hit.kind == "board_cell":
                    row, col = hit.value
                    self._controller.handle_board_cell(row, col)
                else:
                    self._controller.handle_action(hit.value)
        frame = self._renderer.render(
            self._controller.state, self._controller.session
        )
        cv2.imshow(self._window_name, frame)


def build_opencv_client(
    config,
    *,
    language: str = "en",
    locale_directory: str | Path | None = None,
    logger: logging.Logger | None = None,
) -> OpenCvClientApplication:
    policy = EnvelopePolicy(
        config.network.protocol_version,
        config.network.max_message_bytes,
        config.network.request_id_max_length,
        config.network.message_type_max_length,
    )
    directory = (
        Path(locale_directory)
        if locale_directory is not None
        else Path(__file__).resolve().parents[2] / "locales"
    )
    localizer = ClientLocalizer(
        language=language,
        protocol_catalog=LocalizationCatalog(directory),
    )
    transport = WebSocketClientTransport(
        f"ws://{config.network.host}:{config.network.port}", policy
    )
    worker = ClientNetworkWorker(transport)
    events = ClientEventLogger(logger)
    controller = ClientController(
        ClientSessionState(),
        ClientMessageFactory(policy),
        worker,
        localizer,
        ClientUiConstraints.from_config(config),
        snapshot_poll_interval_ms=1000,
        active_snapshot_poll_interval_ms=200,
        events=events,
    )
    if logger is not None:
        events.event("client_started", language=language)
    return OpenCvClientApplication(
        controller, OpenCvClientRenderer(localizer), worker
    )


def run_from_config(
    config_path: str | Path | None = None,
    *,
    language: str = "en",
) -> None:
    path = (
        Path(config_path)
        if config_path is not None
        else Path(__file__).resolve().parents[2] / "config" / "server.json"
    )
    config = ConfigProvider.load(path)
    logger = _configure_client_logger(config)
    build_opencv_client(config, language=language, logger=logger).run()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Kung Fu Chess network client")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to server.json configuration file",
    )
    parser.add_argument(
        "--language",
        default="en",
        choices=("en", "he"),
        help="UI language (en or he)",
    )
    args = parser.parse_args(argv)
    run_from_config(args.config, language=args.language)


if __name__ == "__main__":  # pragma: no cover
    main()
