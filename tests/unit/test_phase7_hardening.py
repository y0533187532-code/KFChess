import asyncio
import json
import logging
from pathlib import Path

import pytest

from kongfu_chess.client.localization import ClientLocalizer
from kongfu_chess.client.screen_renderer import OpenCvClientRenderer
from kongfu_chess.infrastructure.configuration import ConfigProvider
from kongfu_chess.persistence.game_lifecycle_repository import GameLifecycleRepository
from kongfu_chess.persistence.database import SqliteDatabase
from kongfu_chess.persistence.user_repository import UserRepository
from kongfu_chess.server import ConnectionRegistry, build_server_stack


def test_connection_registry_enforces_limit():
    async def scenario():
        registry = ConnectionRegistry(max_connections=2)
        assert await registry.try_add("a", object())
        assert await registry.try_add("b", object())
        assert await registry.try_add("c", object()) is False
        assert await registry.count() == 2

    asyncio.run(scenario())


def test_count_live_games_excludes_terminal_states(tmp_path):
    database = SqliteDatabase(tmp_path / "lifecycle.sqlite3", busy_timeout_ms=5000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    first = users.create(
        username="first",
        password_hash="hash1",
        email="a@example.test",
        phone="0501234567",
        initial_rating=1200,
        now_ms=1,
    )
    second = users.create(
        username="second",
        password_hash="hash2",
        email="b@example.test",
        phone="0501234568",
        initial_rating=1200,
        now_ms=1,
    )
    third = users.create(
        username="third",
        password_hash="hash3",
        email="c@example.test",
        phone="0501234569",
        initial_rating=1200,
        now_ms=1,
    )
    fourth = users.create(
        username="fourth",
        password_hash="hash4",
        email="d@example.test",
        phone="0501234570",
        initial_rating=1200,
        now_ms=1,
    )
    repository = GameLifecycleRepository(database)
    repository.create(
        game_id="live-game",
        mode="PLAY",
        ranked=True,
        state="ACTIVE",
        players=((first.id, "FIRST_PLAYER"), (second.id, "SECOND_PLAYER")),
        now_ms=1000,
    )
    repository.create(
        game_id="ended-game",
        mode="PLAY",
        ranked=True,
        state="ENDED",
        players=((third.id, "FIRST_PLAYER"), (fourth.id, "SECOND_PLAYER")),
        now_ms=1000,
    )
    assert repository.count_live_games() == 1


def test_hebrew_localizer_returns_translated_ui_strings():
    localizer = ClientLocalizer(language="he")
    assert localizer.is_rtl is True
    assert localizer.text("login") == "התחבר"
    assert localizer.text("play") == "שחק"


def test_server_stack_configures_json_logger(tmp_path):
    config_path = Path(__file__).parents[2] / "config" / "server.json"
    document = json.loads(config_path.read_text(encoding="utf-8"))
    document["database"]["path"] = str(tmp_path / "server.sqlite3")
    document["database"]["backup_directory"] = str(tmp_path / "backups")
    document["logging"]["server_path"] = str(tmp_path / "server.jsonl")
    document["logging"]["client_path"] = str(tmp_path / "client.jsonl")
    document["security"]["scrypt_n"] = 1024
    config = ConfigProvider.from_mapping(document, base_directory=tmp_path)
    stack = build_server_stack(config)
    assert stack.logger is not None
    assert isinstance(stack.logger, logging.Logger)
    assert Path(config.logging.server_path).exists()
    log_lines = Path(config.logging.server_path).read_text(encoding="utf-8").splitlines()
    assert any('"event":"server_started"' in line for line in log_lines)


def test_rtl_label_reverses_hebrew_for_opencv(monkeypatch):
    localizer = ClientLocalizer(language="he")
    renderer = OpenCvClientRenderer(localizer)
    captured = []

    def capture_put_text(_frame, text, position, *_args, **_kwargs):
        captured.append((text, position))

    monkeypatch.setattr(
        "kongfu_chess.client.screen_renderer.cv2.putText",
        capture_put_text,
    )
    import numpy as np

    frame = np.zeros((100, 400, 3), dtype=np.uint8)
    renderer._label(frame, "התחברות", 300, 50, 0.8, anchor="right")
    assert captured[0][0] == "תורבחתה"
    assert captured[0][1][0] < 300
