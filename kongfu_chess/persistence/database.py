"""Connection ownership, migrations, transactions, and consistent backups."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .migrations import MIGRATIONS


class SqliteDatabase:
    def __init__(self, path: str | Path, *, busy_timeout_ms: int):
        self._path = Path(path)
        self._busy_timeout_ms = busy_timeout_ms

    def migrate(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied = {
                row["version"]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
            for version, script in MIGRATIONS:
                if version in applied:
                    continue
                connection.executescript(script)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
                )

    @contextmanager
    def transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def backup_to(self, directory: str | Path, *, timestamp_ms: int) -> Path:
        backup_directory = Path(directory)
        backup_directory.mkdir(parents=True, exist_ok=True)
        destination_path = backup_directory / f"kfchess-{timestamp_ms}.sqlite3"
        if destination_path.exists():
            raise FileExistsError(destination_path)
        source = self._connect()
        destination = sqlite3.connect(destination_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return destination_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        return connection
