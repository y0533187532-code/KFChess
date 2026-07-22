"""Launch the production authoritative WebSocket server."""

from .app.server_application import run_from_config


if __name__ == "__main__":  # pragma: no cover
    run_from_config()
