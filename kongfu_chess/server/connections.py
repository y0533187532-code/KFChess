"""Short-lock registry for live sockets; no game state is stored here."""

import asyncio


class ConnectionRegistry:
    def __init__(self):
        self._connections = {}
        self._lock = asyncio.Lock()

    async def add(self, connection_id: str, connection) -> None:
        async with self._lock:
            self._connections[connection_id] = connection

    async def remove(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    async def get(self, connection_id: str):
        async with self._lock:
            return self._connections.get(connection_id)

    async def connection_ids(self) -> tuple[str, ...]:
        async with self._lock:
            return tuple(self._connections)
