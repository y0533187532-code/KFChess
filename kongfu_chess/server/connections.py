"""Short-lock registry for live sockets; no game state is stored here."""

import asyncio


class ConnectionRegistry:
    def __init__(self, *, max_connections: int | None = None):
        self._connections = {}
        self._lock = asyncio.Lock()
        self._max_connections = max_connections

    async def try_add(self, connection_id: str, connection) -> bool:
        async with self._lock:
            if (
                self._max_connections is not None
                and len(self._connections) >= self._max_connections
            ):
                return False
            self._connections[connection_id] = connection
            return True

    async def add(self, connection_id: str, connection) -> None:
        if not await self.try_add(connection_id, connection):
            raise ConnectionLimitError()

    async def remove(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    async def get(self, connection_id: str):
        async with self._lock:
            return self._connections.get(connection_id)

    async def connection_ids(self) -> tuple[str, ...]:
        async with self._lock:
            return tuple(self._connections)

    async def count(self) -> int:
        async with self._lock:
            return len(self._connections)


class ConnectionLimitError(RuntimeError):
    """Raised when the server has reached its WebSocket connection limit."""
