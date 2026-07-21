"""Portable client-side presentation contracts."""

from .auth_ui import (
    AuthAction,
    AuthInputProvider,
    AuthScreen,
    AuthSubmission,
    AuthUiConfig,
    AuthUiMode,
)
from .controller import ClientController
from .localization import ClientLocalizer, ENGLISH_CLIENT_TEXT
from .messages import ClientMessageFactory
from .screen_renderer import OpenCvClientRenderer, UiHit, UiRect
from .session import ClientGameSession, ClientRoomSession, ClientSessionState
from .transport import (
    ClientNetworkWorker,
    ClientTransport,
    TransportResult,
    WebSocketClientTransport,
)
from .ui_state import ClientScreen, ClientUiConstraints, ClientUiState, UiAction

__all__ = [
    "AuthAction",
    "AuthInputProvider",
    "AuthScreen",
    "AuthSubmission",
    "AuthUiConfig",
    "AuthUiMode",
    "ClientController",
    "ClientGameSession",
    "ClientLocalizer",
    "ClientMessageFactory",
    "ClientNetworkWorker",
    "ClientRoomSession",
    "ClientScreen",
    "ClientSessionState",
    "ClientTransport",
    "ClientUiConstraints",
    "ClientUiState",
    "ENGLISH_CLIENT_TEXT",
    "OpenCvClientRenderer",
    "TransportResult",
    "UiAction",
    "UiHit",
    "UiRect",
    "WebSocketClientTransport",
]
