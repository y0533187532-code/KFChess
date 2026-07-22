"""Per-game FIFO command processor enforcing the single-writer invariant."""

from __future__ import annotations

import asyncio
import inspect
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ...protocol.error_codes import ProtocolErrorCode


class SessionClosedError(RuntimeError):
    pass


class SessionCommandType(str, Enum):
    MOVE = "move"
    JUMP = "jump"
    SNAPSHOT = "snapshot"
    TICK = "tick"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class SessionCommand:
    kind: str
    request_id: str | None
    payload: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True)
class HandlerResult:
    accepted: bool
    changed: bool
    code: str
    payload: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True)
class CommandResult:
    request_id: str | None
    accepted: bool
    code: str
    sequence: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class _QueuedCommand:
    command: SessionCommand
    future: asyncio.Future


_STOP = object()


class GameSession:
    """Serialize every mutation through one task without locking the engine."""

    def __init__(
        self,
        game_id: str,
        handlers: Mapping[str, Callable[[SessionCommand], HandlerResult]],
        *,
        initial_sequence: int,
        request_cache_size: int,
        on_sequence_changed=None,
    ):
        if request_cache_size < 1:
            raise ValueError("request_cache_size must be positive")
        self._game_id = game_id
        self._handlers = MappingProxyType(dict(handlers))
        self._sequence = initial_sequence
        self._request_cache_size = request_cache_size
        self._on_sequence_changed = on_sequence_changed
        self._queue: asyncio.Queue = asyncio.Queue()
        self._pending: dict[str, asyncio.Future] = {}
        self._completed: OrderedDict[str, CommandResult] = OrderedDict()
        self._worker_task: asyncio.Task | None = None
        self._closed = False
        self._paused = False

    @property
    def game_id(self) -> str:
        return self._game_id

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def is_running(self) -> bool:
        return self._worker_task is not None and not self._worker_task.done()

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        if self._closed:
            raise SessionClosedError("GameSession is closed")
        self._paused = True

    def resume(self) -> None:
        if self._closed:
            raise SessionClosedError("GameSession is closed")
        self._paused = False

    def start(self) -> None:
        if self._closed:
            raise SessionClosedError("GameSession is closed")
        if self.is_running:
            return
        self._worker_task = asyncio.create_task(
            self._run(), name=f"game-session:{self._game_id}"
        )

    async def submit(self, command: SessionCommand) -> CommandResult:
        if self._closed:
            raise SessionClosedError("GameSession is closed")
        if not self.is_running:
            raise RuntimeError("GameSession must be started before submit")

        request_id = command.request_id
        if request_id is not None:
            completed = self._completed.get(request_id)
            if completed is not None:
                self._completed.move_to_end(request_id)
                return completed
            pending = self._pending.get(request_id)
            if pending is not None:
                return await asyncio.shield(pending)

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        if request_id is not None:
            self._pending[request_id] = future
        self._queue.put_nowait(_QueuedCommand(command, future))
        return await asyncio.shield(future)

    async def close(self) -> None:
        if self._closed:
            if self._worker_task is not None:
                await self._worker_task
            return
        self._closed = True
        if self._worker_task is None:
            return
        self._queue.put_nowait(_STOP)
        await self._worker_task

    async def _run(self) -> None:
        while True:
            queued = await self._queue.get()
            try:
                if queued is _STOP:
                    return
                await self._process(queued)
            finally:
                self._queue.task_done()

    async def _process(self, queued: _QueuedCommand) -> None:
        command = queued.command
        try:
            if self._paused and command.kind in {
                SessionCommandType.MOVE.value,
                SessionCommandType.JUMP.value,
                SessionCommandType.TICK.value,
            }:
                handled = HandlerResult(
                    accepted=False,
                    changed=False,
                    code=ProtocolErrorCode.GAME_PAUSED.value,
                )
            elif (handler := self._handlers.get(command.kind)) is None:
                handled = HandlerResult(
                    accepted=False,
                    changed=False,
                    code=ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE.value,
                )
            else:
                handled = handler(command)
                if inspect.isawaitable(handled):
                    handled = await handled
                if not isinstance(handled, HandlerResult):
                    raise TypeError("GameSession handlers must return HandlerResult")
            if handled.changed:
                self._sequence += 1
                if self._on_sequence_changed is not None:
                    callback = self._on_sequence_changed(
                        self._game_id,
                        self._sequence,
                        dict(handled.payload),
                    )
                    if inspect.isawaitable(callback):
                        await callback
            result = CommandResult(
                request_id=command.request_id,
                accepted=handled.accepted,
                code=handled.code,
                sequence=self._sequence,
                payload=MappingProxyType(dict(handled.payload)),
            )
        except Exception as exc:
            self._finish_failed(command.request_id, queued.future, exc)
            return

        if command.request_id is not None:
            self._pending.pop(command.request_id, None)
            self._completed[command.request_id] = result
            while len(self._completed) > self._request_cache_size:
                self._completed.popitem(last=False)
        if not queued.future.done():
            queued.future.set_result(result)

    def _finish_failed(
        self,
        request_id: str | None,
        future: asyncio.Future,
        error: Exception,
    ) -> None:
        if request_id is not None:
            self._pending.pop(request_id, None)
        if not future.done():
            future.set_exception(error)
