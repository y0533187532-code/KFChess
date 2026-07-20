"""Typed loading and validation for client/server operational configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ConfigError(ValueError):
    """Raised when an external configuration document is incomplete or invalid."""


@dataclass(frozen=True)
class NetworkConfig:
    host: str
    port: int
    protocol_version: str
    max_message_bytes: int
    request_id_max_length: int
    message_type_max_length: int
    request_cache_size: int
    initial_sequence: int


@dataclass(frozen=True)
class TimingConfig:
    tick_interval_ms: int
    matchmaking_timeout_seconds: int
    reconnect_grace_seconds: int
    room_close_delay_seconds: int
    auth_token_ttl_seconds: int


@dataclass(frozen=True)
class EloConfig:
    initial_rating: int
    scale: int
    k_factor: int
    rating_floor: int
    matchmaking_range: int


@dataclass(frozen=True)
class CapacityConfig:
    active_games: int
    matchmaking_users: int
    open_rooms: int
    spectators_per_room: int
    websocket_connections: int


@dataclass(frozen=True)
class DatabaseConfig:
    path: Path
    backup_directory: Path
    backup_interval_hours: int
    busy_timeout_ms: int


@dataclass(frozen=True)
class LoggingConfig:
    server_path: Path
    client_path: Path
    level: str
    retention_days: int
    max_bytes: int
    backup_count: int
    debug_payloads: bool


@dataclass(frozen=True)
class SecurityConfig:
    token_bytes: int
    username_min_length: int
    username_max_length: int
    password_min_length: int


@dataclass(frozen=True)
class AppConfig:
    network: NetworkConfig
    timing: TimingConfig
    elo: EloConfig
    capacity: CapacityConfig
    database: DatabaseConfig
    logging: LoggingConfig
    security: SecurityConfig


class ConfigProvider:
    """Load a complete configuration document without silent defaults."""

    _LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

    @classmethod
    def load(cls, path: str | Path) -> AppConfig:
        config_path = Path(path)
        try:
            document = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Cannot load configuration: {exc}") from exc
        if not isinstance(document, dict):
            raise ConfigError("Configuration root must be an object")
        return cls.from_mapping(document, base_directory=config_path.parent)

    @classmethod
    def from_mapping(
        cls,
        document: Mapping[str, Any],
        *,
        base_directory: str | Path = ".",
    ) -> AppConfig:
        root = Path(base_directory)
        network = cls._section(document, "network")
        timing = cls._section(document, "timing")
        elo = cls._section(document, "elo")
        capacity = cls._section(document, "capacity")
        database = cls._section(document, "database")
        logging_values = cls._section(document, "logging")
        security = cls._section(document, "security")

        level = cls._string(logging_values, "level").upper()
        if level not in cls._LOG_LEVELS:
            raise ConfigError("logging.level is not a supported level")

        return AppConfig(
            network=NetworkConfig(
                host=cls._string(network, "host"),
                port=cls._integer(network, "port", minimum=1, maximum=65535),
                protocol_version=cls._string(network, "protocol_version"),
                max_message_bytes=cls._integer(
                    network, "max_message_bytes", minimum=1
                ),
                request_id_max_length=cls._integer(
                    network, "request_id_max_length", minimum=1
                ),
                message_type_max_length=cls._integer(
                    network, "message_type_max_length", minimum=1
                ),
                request_cache_size=cls._integer(
                    network, "request_cache_size", minimum=1
                ),
                initial_sequence=cls._integer(
                    network, "initial_sequence", minimum=0
                ),
            ),
            timing=TimingConfig(
                tick_interval_ms=cls._integer(
                    timing, "tick_interval_ms", minimum=1
                ),
                matchmaking_timeout_seconds=cls._integer(
                    timing, "matchmaking_timeout_seconds", minimum=1
                ),
                reconnect_grace_seconds=cls._integer(
                    timing, "reconnect_grace_seconds", minimum=1
                ),
                room_close_delay_seconds=cls._integer(
                    timing, "room_close_delay_seconds", minimum=0
                ),
                auth_token_ttl_seconds=cls._integer(
                    timing, "auth_token_ttl_seconds", minimum=1
                ),
            ),
            elo=EloConfig(
                initial_rating=cls._integer(elo, "initial_rating", minimum=1),
                scale=cls._integer(elo, "scale", minimum=1),
                k_factor=cls._integer(elo, "k_factor", minimum=1),
                rating_floor=cls._integer(elo, "rating_floor", minimum=0),
                matchmaking_range=cls._integer(
                    elo, "matchmaking_range", minimum=0
                ),
            ),
            capacity=CapacityConfig(
                active_games=cls._integer(capacity, "active_games", minimum=1),
                matchmaking_users=cls._integer(
                    capacity, "matchmaking_users", minimum=1
                ),
                open_rooms=cls._integer(capacity, "open_rooms", minimum=1),
                spectators_per_room=cls._integer(
                    capacity, "spectators_per_room", minimum=0
                ),
                websocket_connections=cls._integer(
                    capacity, "websocket_connections", minimum=1
                ),
            ),
            database=DatabaseConfig(
                path=cls._path(root, database, "path"),
                backup_directory=cls._path(root, database, "backup_directory"),
                backup_interval_hours=cls._integer(
                    database, "backup_interval_hours", minimum=1
                ),
                busy_timeout_ms=cls._integer(
                    database, "busy_timeout_ms", minimum=1
                ),
            ),
            logging=LoggingConfig(
                server_path=cls._path(root, logging_values, "server_path"),
                client_path=cls._path(root, logging_values, "client_path"),
                level=level,
                retention_days=cls._integer(
                    logging_values, "retention_days", minimum=1
                ),
                max_bytes=cls._integer(logging_values, "max_bytes", minimum=1),
                backup_count=cls._integer(
                    logging_values, "backup_count", minimum=1
                ),
                debug_payloads=cls._boolean(logging_values, "debug_payloads"),
            ),
            security=SecurityConfig(
                token_bytes=cls._integer(security, "token_bytes", minimum=16),
                username_min_length=cls._integer(
                    security, "username_min_length", minimum=1
                ),
                username_max_length=cls._integer(
                    security, "username_max_length", minimum=1
                ),
                password_min_length=cls._integer(
                    security, "password_min_length", minimum=1
                ),
            ),
        )

    @staticmethod
    def _section(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        value = document.get(key)
        if not isinstance(value, dict):
            raise ConfigError(f"{key} must be an object")
        return value

    @staticmethod
    def _string(section: Mapping[str, Any], key: str) -> str:
        value = section.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _integer(
        section: Mapping[str, Any],
        key: str,
        *,
        minimum: int,
        maximum: int | None = None,
    ) -> int:
        value = section.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{key} must be an integer")
        if value < minimum or (maximum is not None and value > maximum):
            bounds = f"{minimum}..{maximum}" if maximum is not None else f">={minimum}"
            raise ConfigError(f"{key} must be {bounds}")
        return value

    @staticmethod
    def _boolean(section: Mapping[str, Any], key: str) -> bool:
        value = section.get(key)
        if not isinstance(value, bool):
            raise ConfigError(f"{key} must be a boolean")
        return value

    @classmethod
    def _path(cls, root: Path, section: Mapping[str, Any], key: str) -> Path:
        path = Path(cls._string(section, key))
        return path if path.is_absolute() else (root / path).resolve()
