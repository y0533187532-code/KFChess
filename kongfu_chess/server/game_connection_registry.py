"""Map live WebSocket connections to active game sessions for snapshot push."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class GameConnection:
    connection_id: str
    game_id: str
    user_id: int


class GameConnectionRegistry:
    """Thread-safe lookup of which sockets belong to which active games."""

    def __init__(self):
        self._by_connection: dict[str, GameConnection] = {}
        self._by_game: dict[str, set[str]] = {}
        self._lock = RLock()

    def bind(self, connection_id: str, game_id: str, user_id: int) -> None:
        with self._lock:
            self._unbind_locked(connection_id)
            self._by_connection[connection_id] = GameConnection(
                connection_id, game_id, user_id
            )
            self._by_game.setdefault(game_id, set()).add(connection_id)

    def unbind(self, connection_id: str) -> None:
        with self._lock:
            self._unbind_locked(connection_id)

    def remove_connection(self, connection_id: str) -> None:
        self.unbind(connection_id)

    def pop_connection(self, connection_id: str) -> GameConnection | None:
        with self._lock:
            existing = self._by_connection.pop(connection_id, None)
            if existing is None:
                return None
            game_connections = self._by_game.get(existing.game_id)
            if game_connections is not None:
                game_connections.discard(connection_id)
                if not game_connections:
                    self._by_game.pop(existing.game_id, None)
            return existing

    def connections_for(self, game_id: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._by_game.get(game_id, ())))

    def _unbind_locked(self, connection_id: str) -> None:
        existing = self._by_connection.pop(connection_id, None)
        if existing is None:
            return
        game_connections = self._by_game.get(existing.game_id)
        if game_connections is None:
            return
        game_connections.discard(connection_id)
        if not game_connections:
            self._by_game.pop(existing.game_id, None)
