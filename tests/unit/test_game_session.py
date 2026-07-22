import asyncio

import pytest

from kongfu_chess.server import (
    GameSession,
    HandlerResult,
    SessionClosedError,
    SessionCommand,
    SessionCommandType,
)


def run(coro):
    return asyncio.run(coro)


def test_all_mutation_kinds_share_one_fifo_worker_and_sequence():
    async def scenario():
        observed = []
        active_handlers = 0
        max_active_handlers = 0

        async def handler(command):
            nonlocal active_handlers, max_active_handlers
            active_handlers += 1
            max_active_handlers = max(max_active_handlers, active_handlers)
            await asyncio.sleep(0)
            observed.append(command.kind)
            active_handlers -= 1
            return HandlerResult(True, True, "ok")

        kinds = [item.value for item in SessionCommandType]
        session = GameSession(
            "game-1",
            {kind: handler for kind in kinds},
            initial_sequence=0,
            request_cache_size=32,
        )
        session.start()
        tasks = [
            asyncio.create_task(
                session.submit(SessionCommand(kind, f"request-{index}"))
            )
            for index, kind in enumerate(kinds)
        ]
        results = await asyncio.gather(*tasks)
        await session.close()
        return kinds, observed, max_active_handlers, results

    kinds, observed, max_active_handlers, results = run(scenario())

    assert observed == kinds
    assert max_active_handlers == 1
    assert [result.sequence for result in results] == list(range(1, len(kinds) + 1))


def test_concurrent_duplicate_request_executes_handler_once():
    async def scenario():
        calls = 0

        async def handler(_command):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return HandlerResult(True, True, "ok", {"value": 7})

        session = GameSession(
            "game-1", {"tick": handler}, initial_sequence=4, request_cache_size=8
        )
        session.start()
        command = SessionCommand("tick", "same-request")
        first, second = await asyncio.gather(
            session.submit(command), session.submit(command)
        )
        third = await session.submit(command)
        await session.close()
        return calls, first, second, third

    calls, first, second, third = run(scenario())

    assert calls == 1
    assert first is second is third
    assert first.sequence == 5


def test_rejected_command_does_not_advance_sequence():
    async def scenario():
        def reject(_command):
            return HandlerResult(False, False, "game_paused")

        session = GameSession(
            "game-1", {"move": reject}, initial_sequence=9, request_cache_size=8
        )
        session.start()
        result = await session.submit(SessionCommand("move", "request-1"))
        await session.close()
        return session.sequence, result

    sequence, result = run(scenario())

    assert sequence == result.sequence == 9
    assert result.accepted is False


def test_unknown_command_is_rejected_without_handler_or_sequence_change():
    async def scenario():
        session = GameSession(
            "game-1", {}, initial_sequence=2, request_cache_size=8
        )
        session.start()
        result = await session.submit(SessionCommand("not_registered", "request-1"))
        await session.close()
        return result

    result = run(scenario())

    assert result.accepted is False
    assert result.code == "unknown_message_type"
    assert result.sequence == 2


def test_close_drains_queued_work_and_rejects_new_submissions():
    async def scenario():
        async def handler(_command):
            await asyncio.sleep(0)
            return HandlerResult(True, True, "ok")

        session = GameSession(
            "game-1", {"tick": handler}, initial_sequence=0, request_cache_size=8
        )
        session.start()
        pending = asyncio.create_task(
            session.submit(SessionCommand("tick", request_id=None))
        )
        await asyncio.sleep(0)
        await session.close()
        result = await pending
        with pytest.raises(SessionClosedError):
            await session.submit(SessionCommand("tick", request_id=None))
        return result, session.is_running

    result, is_running = run(scenario())

    assert result.sequence == 1
    assert is_running is False


def test_pause_gate_rejects_mutations_without_calling_handler_or_advancing_sequence():
    async def scenario():
        calls = 0

        def handler(_command):
            nonlocal calls
            calls += 1
            return HandlerResult(True, True, "ok")

        session = GameSession(
            "game-1", {"move": handler}, initial_sequence=3, request_cache_size=8
        )
        session.start()
        session.pause()
        paused = await session.submit(SessionCommand("move", "paused-request"))
        session.resume()
        resumed = await session.submit(SessionCommand("move", "resumed-request"))
        await session.close()
        return calls, paused, resumed

    calls, paused, resumed = run(scenario())

    assert paused.accepted is False
    assert paused.code == "game_paused"
    assert paused.sequence == 3
    assert resumed.accepted is True
    assert resumed.sequence == 4
    assert calls == 1


def test_request_cache_size_must_be_positive():
    with pytest.raises(ValueError, match="request_cache_size must be positive"):
        GameSession(
            "game-1",
            {},
            initial_sequence=0,
            request_cache_size=0,
        )


def test_pause_and_resume_raise_after_close():
    async def scenario():
        session = GameSession(
            "game-1", {}, initial_sequence=0, request_cache_size=8
        )
        session.start()
        await session.close()
        return session

    session = run(scenario())
    with pytest.raises(SessionClosedError):
        session.pause()
    with pytest.raises(SessionClosedError):
        session.resume()


def test_start_raises_after_close():
    async def scenario():
        session = GameSession(
            "game-1", {}, initial_sequence=0, request_cache_size=8
        )
        session.start()
        await session.close()
        return session

    session = run(scenario())
    with pytest.raises(SessionClosedError):
        session.start()


def test_submit_before_start_raises():
    async def scenario():
        session = GameSession(
            "game-1", {}, initial_sequence=0, request_cache_size=8
        )
        with pytest.raises(RuntimeError, match="must be started"):
            await session.submit(SessionCommand("tick", "request-1"))

    run(scenario())


def test_handler_exception_propagates_to_caller():
    async def scenario():
        def broken(_command):
            raise ValueError("boom")

        session = GameSession(
            "game-1",
            {"tick": broken},
            initial_sequence=0,
            request_cache_size=8,
        )
        session.start()
        with pytest.raises(ValueError, match="boom"):
            await session.submit(SessionCommand("tick", "request-1"))
        await session.close()

    run(scenario())


def test_sequence_changed_callback_runs_for_mutations():
    async def scenario():
        observed = []

        def handler(_command):
            return HandlerResult(True, True, "ok", {"tick": 1})

        session = GameSession(
            "game-1",
            {"tick": handler},
            initial_sequence=4,
            request_cache_size=8,
            on_sequence_changed=lambda game_id, sequence, payload: observed.append(
                (game_id, sequence, payload)
            ),
        )
        session.start()
        result = await session.submit(SessionCommand("tick", "request-1"))
        await session.close()
        return observed, result

    observed, result = run(scenario())

    assert result.sequence == 5
    assert observed == [("game-1", 5, {"tick": 1})]


def test_async_sequence_changed_callback_is_awaited():
    async def scenario():
        observed = []

        async def on_sequence_changed(game_id, sequence, payload):
            await asyncio.sleep(0)
            observed.append((game_id, sequence, payload))

        def handler(_command):
            return HandlerResult(True, True, "ok")

        session = GameSession(
            "game-1",
            {"tick": handler},
            initial_sequence=0,
            request_cache_size=8,
            on_sequence_changed=on_sequence_changed,
        )
        session.start()
        await session.submit(SessionCommand("tick", "request-1"))
        await session.close()
        return observed

    observed = run(scenario())
    assert observed == [("game-1", 1, {})]


def test_completed_request_cache_evicts_oldest_entries():
    async def scenario():
        calls = []

        def handler(command):
            calls.append(command.request_id)
            return HandlerResult(True, True, "ok")

        session = GameSession(
            "game-1",
            {"tick": handler},
            initial_sequence=0,
            request_cache_size=2,
        )
        session.start()
        await session.submit(SessionCommand("tick", "request-1"))
        await session.submit(SessionCommand("tick", "request-2"))
        await session.submit(SessionCommand("tick", "request-3"))
        await session.submit(SessionCommand("tick", "request-1"))
        await session.close()
        return calls

    calls = run(scenario())
    assert calls == ["request-1", "request-2", "request-3", "request-1"]
