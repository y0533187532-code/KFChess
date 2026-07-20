import json
import logging
import os
import time

from kongfu_chess.infrastructure.structured_logging import (
    REDACTED,
    JsonLinesFormatter,
    configure_json_logger,
    redact,
)


def test_redact_masks_sensitive_values_recursively():
    safe = redact(
        {
            "user_id": 7,
            "payload": {
                "password": "open-sesame",
                "auth_token": "plain-token",
                "profile": {"email": "a@example.test", "phone": "0500000000"},
            },
        }
    )

    assert safe["user_id"] == 7
    assert safe["payload"]["password"] == REDACTED
    assert safe["payload"]["auth_token"] == REDACTED
    assert safe["payload"]["profile"] == {
        "email": REDACTED,
        "phone": REDACTED,
    }


def test_json_lines_formatter_emits_stable_fields_and_masks_extras():
    record = logging.LogRecord(
        name="server",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ignored-message",
        args=(),
        exc_info=None,
    )
    record.event = "login_failed"
    record.request_id = "request-1"
    record.password_hash = "private"

    output = json.loads(JsonLinesFormatter().format(record))

    assert output["event"] == "login_failed"
    assert output["request_id"] == "request-1"
    assert output["password_hash"] == REDACTED
    assert output["timestamp"].endswith("Z")


def test_configured_logger_writes_one_json_object_per_line(tmp_path):
    log_path = tmp_path / "server.jsonl"
    logger = configure_json_logger(
        "test.kfchess.structured",
        log_path,
        level="INFO",
        max_bytes=4096,
        backup_count=2,
        retention_days=14,
    )

    logger.info("connected", extra={"event": "connected", "game_id": "g-1"})
    for handler in logger.handlers:
        handler.flush()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["game_id"] == "g-1"


def test_configured_logger_removes_rotations_older_than_retention(tmp_path):
    log_path = tmp_path / "server.jsonl"
    old_rotation = tmp_path / "server.jsonl.1"
    old_rotation.write_text("old\n", encoding="utf-8")
    old_timestamp = time.time() - 15 * 24 * 60 * 60
    os.utime(old_rotation, (old_timestamp, old_timestamp))

    configure_json_logger(
        "test.kfchess.retention",
        log_path,
        level="INFO",
        max_bytes=4096,
        backup_count=2,
        retention_days=14,
    )

    assert old_rotation.exists() is False
