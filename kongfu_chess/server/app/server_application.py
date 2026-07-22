"""Production server composition: persistence, runtime, routing, and WebSocket gateway."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from ...infrastructure.configuration import AppConfig, ConfigProvider
from ...infrastructure.structured_logging import configure_json_logger
from ...persistence import (
    AuthSessionRepository,
    GameLifecycleRepository,
    GameTokenRepository,
    MatchRepository,
    RoomRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from ...protocol import EnvelopePolicy, serialize_game_snapshot
from ..auth.auth_handlers import AuthHandlers
from ..auth.auth_service import AuthService
from ..auth.password_hasher import PasswordHasher
from ..core.event_logger import ServerEventLogger
from ..gameplay.game_runtime_factory import GameRuntimeFactory
from ..gameplay.gameplay_handlers import GameplayHandlers
from ..gameplay.gameplay_service import GameplayCommandService, GameSessionRegistry
from ..gameplay.tick_scheduler import TickScheduler
from ..lifecycle.game_lifecycle_handlers import GameLifecycleHandlers
from ..lifecycle.game_lifecycle_service import GameLifecycleService
from ..lifecycle.lifecycle_push_service import LifecyclePushService
from ..matchmaking.elo_service import EloService
from ..matchmaking.matchmaking_handlers import MatchmakingHandlers
from ..matchmaking.matchmaking_service import MatchmakingService
from ..rooms.rooms_handlers import RoomsHandlers
from ..rooms.rooms_service import RoomsService
from ..transport.connections import ConnectionRegistry
from ..transport.game_connection_registry import GameConnectionRegistry
from ..transport.snapshot_push_service import SnapshotPushService
from ..transport.websocket_gateway import WebSocketGateway
from .routing import MessageRouter


def _clock_ms() -> int:
    return time.time_ns() // 1_000_000


@dataclass
class ServerStack:
    config: AppConfig
    database: SqliteDatabase
    auth: AuthService
    lifecycle: GameLifecycleService
    registry: GameSessionRegistry
    runtime_factory: GameRuntimeFactory
    gateway: WebSocketGateway
    router: MessageRouter
    game_connections: GameConnectionRegistry
    connections: ConnectionRegistry
    lifecycle_push: LifecyclePushService | None = None
    logger: logging.Logger | None = None
    _expiry_task: asyncio.Task | None = field(default=None, repr=False)
    _backup_task: asyncio.Task | None = field(default=None, repr=False)

    def start_background_tasks(self) -> None:
        if self._expiry_task is None:
            self._expiry_task = asyncio.create_task(
                _run_lifecycle_expiry(self),
                name="lifecycle-expiry",
            )
        if self._backup_task is None:
            self._backup_task = asyncio.create_task(
                _run_database_backup(self),
                name="database-backup",
            )

    async def stop_background_tasks(self) -> None:
        for task_name in ("_expiry_task", "_backup_task"):
            task = getattr(self, task_name)
            if task is None:
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            setattr(self, task_name, None)


def _configure_server_logger(config: AppConfig) -> logging.Logger:
    return configure_json_logger(
        "kfchess.server",
        config.logging.server_path,
        level=config.logging.level,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        retention_days=config.logging.retention_days,
    )


def _open_database(config: AppConfig) -> SqliteDatabase:
    database = SqliteDatabase(
        config.database.path,
        busy_timeout_ms=config.database.busy_timeout_ms,
    )
    database.migrate()
    return database


def _build_repositories(database: SqliteDatabase, config: AppConfig):
    users = UserRepository(
        database,
        username_min_length=config.security.username_min_length,
        username_max_length=config.security.username_max_length,
    )
    tokens = TokenService(
        AuthSessionRepository(database),
        GameTokenRepository(database),
        token_bytes=config.security.token_bytes,
    )
    passwords = PasswordHasher(
        salt_bytes=config.security.password_salt_bytes,
        n=config.security.scrypt_n,
        r=config.security.scrypt_r,
        p=config.security.scrypt_p,
        hash_bytes=config.security.password_hash_bytes,
    )
    auth = AuthService(
        users,
        tokens,
        passwords,
        password_min_length=config.security.password_min_length,
        initial_rating=config.elo.initial_rating,
        auth_token_ttl_seconds=config.timing.auth_token_ttl_seconds,
    )
    return (
        auth,
        users,
        tokens,
        GameLifecycleRepository(database),
        MatchRepository(database),
        RoomRepository(database),
    )


def build_server_stack(config: AppConfig) -> ServerStack:
    """Wire persistence, authoritative runtime, handlers, and the WebSocket gateway."""

    logger = _configure_server_logger(config)
    events = ServerEventLogger(logger)

    database = _open_database(config)
    auth, users, tokens, lifecycle_repo, match_repo, rooms_repo = _build_repositories(
        database, config
    )
    elo = EloService.from_config(config)
    policy = EnvelopePolicy(
        config.network.protocol_version,
        config.network.max_message_bytes,
        config.network.request_id_max_length,
        config.network.message_type_max_length,
    )

    registry = GameSessionRegistry()
    scheduler = TickScheduler(
        tick_interval_ms=config.timing.tick_interval_ms,
        clock_ms=_clock_ms,
    )
    game_connections = GameConnectionRegistry()
    connections = ConnectionRegistry(
        max_connections=config.capacity.websocket_connections
    )
    router = MessageRouter()

    lifecycle_holder: dict[str, GameLifecycleService] = {}
    push_holder: dict[str, LifecyclePushService] = {}

    async def on_connection_closed(binding) -> None:
        lifecycle = lifecycle_holder.get("service")
        if lifecycle is None:
            return
        view = lifecycle.disconnect_transport(
            binding.game_id,
            binding.user_id,
            now_ms=_clock_ms(),
        )
        if view is None:
            return
        events.event(
            "transport_disconnect",
            game_id=binding.game_id,
            user_id=binding.user_id,
            state=view.state.value,
        )
        lifecycle_push = push_holder.get("service")
        if lifecycle_push is not None:
            await lifecycle_push.notify_view(
                view.game_id,
                view,
                now_ms=_clock_ms(),
                paused_message=True,
                exclude=(binding.connection_id,),
            )

    gateway = WebSocketGateway(
        connections,
        router,
        policy,
        game_connections=game_connections,
        logger=logger,
        on_connection_closed=on_connection_closed,
    )
    push_service = SnapshotPushService(
        gateway,
        game_connections,
        policy,
        clock_ms=_clock_ms,
    )
    lifecycle_push = LifecyclePushService(
        gateway,
        game_connections,
        clock_ms=_clock_ms,
    )
    push_holder["service"] = lifecycle_push

    runtime_factory = GameRuntimeFactory(
        registry,
        scheduler,
        initial_sequence=config.network.initial_sequence,
        request_cache_size=config.network.request_cache_size,
        push_service=push_service,
    )
    lifecycle = GameLifecycleService(
        auth,
        tokens,
        lifecycle_repo,
        users,
        match_repo,
        elo,
        reconnect_grace_seconds=config.timing.reconnect_grace_seconds,
        runtime_factory=runtime_factory,
        room_repository=rooms_repo,
        max_active_games=config.capacity.active_games,
    )
    runtime_factory.bind_lifecycle(lifecycle)
    lifecycle_holder["service"] = lifecycle

    matchmaking = MatchmakingService.from_config(
        auth,
        tokens,
        config,
        lifecycle_service=lifecycle,
    )
    lifecycle.set_terminal_listener(matchmaking.release_game)

    def snapshot_provider(game_id: str):
        engine = runtime_factory.engine_for(game_id)
        if engine is None:
            return None
        return serialize_game_snapshot(engine.snapshot())

    rooms = RoomsService.from_config(
        auth,
        tokens,
        rooms_repo,
        config,
        lifecycle_service=lifecycle,
        snapshot_provider=snapshot_provider,
        active_game_checker=lifecycle.user_in_active_game,
    )
    gameplay = GameplayCommandService(
        auth,
        tokens,
        registry,
        lifecycle_service=lifecycle,
    )

    AuthHandlers(auth, clock_ms=_clock_ms, events=events).register_routes(router)
    MatchmakingHandlers(
        matchmaking, clock_ms=_clock_ms, events=events
    ).register_routes(router)
    RoomsHandlers(rooms, clock_ms=_clock_ms, events=events).register_routes(router)
    GameLifecycleHandlers(
        lifecycle,
        clock_ms=_clock_ms,
        game_connections=game_connections,
        lifecycle_push=lifecycle_push,
        events=events,
    ).register_routes(router)
    GameplayHandlers(
        gameplay,
        clock_ms=_clock_ms,
        game_connections=game_connections,
        events=events,
    ).register_routes(router)

    now_ms = _clock_ms()
    rooms.recover_after_restart(now_ms=now_ms)
    lifecycle.recover_after_restart(now_ms=now_ms)

    events.event(
        "server_started",
        host=config.network.host,
        port=config.network.port,
        database_path=str(config.database.path),
    )

    return ServerStack(
        config=config,
        database=database,
        auth=auth,
        lifecycle=lifecycle,
        registry=registry,
        runtime_factory=runtime_factory,
        gateway=gateway,
        router=router,
        game_connections=game_connections,
        lifecycle_push=lifecycle_push,
        logger=logger,
        connections=connections,
    )


async def _run_lifecycle_expiry(stack: ServerStack) -> None:
    try:
        while True:
            now_ms = _clock_ms()
            changed = stack.lifecycle.expire(now_ms=now_ms)
            if changed and stack.lifecycle_push is not None:
                await stack.lifecycle_push.notify_views(changed, now_ms=now_ms)
                events = ServerEventLogger(stack.logger)
                for view in changed:
                    if view.state.value in {"ENDED", "CANCELLED", "INTERRUPTED"}:
                        events.event(
                            "game_terminal",
                            game_id=view.game_id,
                            state=view.state.value,
                            reason=view.terminal_reason,
                        )
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        raise


async def _run_database_backup(stack: ServerStack) -> None:
    events = ServerEventLogger(stack.logger)
    interval_seconds = stack.config.database.backup_interval_hours * 3600
    try:
        while True:
            now_ms = _clock_ms()
            try:
                backup_path = await asyncio.to_thread(
                    stack.database.backup_to,
                    stack.config.database.backup_directory,
                    timestamp_ms=now_ms,
                )
            except Exception as exc:
                events.event("backup_failed", error=str(exc))
            else:
                events.event("backup_completed", path=str(backup_path))
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        raise


async def serve_forever(stack: ServerStack) -> None:
    """Start the gateway and block until cancelled."""

    await stack.gateway.start(stack.config.network.host, stack.config.network.port)
    stack.start_background_tasks()
    await asyncio.Future()


async def shutdown_stack(stack: ServerStack) -> None:
    """Stop active games and close the WebSocket listener."""

    await stack.stop_background_tasks()
    for game_id in stack.registry.game_ids():
        stack.runtime_factory.teardown(game_id)
    await stack.gateway.stop()
    ServerEventLogger(stack.logger).event("server_stopped")


def run_from_config(config_path: str | Path | None = None) -> None:
    path = (
        Path(config_path)
        if config_path is not None
        else Path(__file__).resolve().parents[2] / "config" / "server.json"
    )

    async def main() -> None:
        stack = build_server_stack(ConfigProvider.load(path))
        try:
            await serve_forever(stack)
        finally:
            await shutdown_stack(stack)

    asyncio.run(main())
