from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover - exercised only when optional packaging is broken.
    psycopg = None
    dict_row = None
    Json = None


class DatabaseConnection:
    def __init__(self, connection: Any, dialect: str) -> None:
        self.connection = connection
        self.dialect = dialect

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None):
        return self.connection.execute(self._sql(sql), params or ())

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()

    def _sql(self, sql: str) -> str:
        if self.dialect == "postgres":
            return sql.replace("?", "%s")
        return sql


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = _normalize_database_url(database_url)
        if self.database_url.startswith("sqlite:///"):
            self.dialect = "sqlite"
            self.path = self.database_url.removeprefix("sqlite:///")
        elif self.database_url.startswith("postgresql://"):
            self.dialect = "postgres"
            self.path = None
        else:
            raise ValueError("DATABASE_URL must start with sqlite:///, postgres://, or postgresql://")

    def connect(self) -> DatabaseConnection:
        if self.dialect == "sqlite":
            assert self.path is not None
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            raw_connection = sqlite3.connect(self.path)
            raw_connection.row_factory = sqlite3.Row
        else:
            if psycopg is None:
                raise RuntimeError("psycopg is required for PostgreSQL DATABASE_URL values")
            raw_connection = psycopg.connect(self.database_url, row_factory=dict_row)

        connection = DatabaseConnection(raw_connection, self.dialect)
        self.ensure_schema(connection)
        return connection

    def json_value(self, value: Any) -> Any:
        if self.dialect == "postgres":
            if Json is None:
                raise RuntimeError("psycopg is required for PostgreSQL JSON values")
            return Json(value)
        return value

    def ensure_schema(self, connection: DatabaseConnection) -> None:
        if self.dialect == "postgres":
            self._ensure_postgres_schema(connection)
        else:
            self._ensure_sqlite_schema(connection)
        connection.commit()

    def _ensure_sqlite_schema(self, connection: DatabaseConnection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                recommendation_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                actor_id TEXT PRIMARY KEY,
                email TEXT,
                display_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_audit_log (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_status TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                request_payload TEXT NOT NULL,
                response_payload TEXT,
                error_code TEXT,
                error_message TEXT,
                runtime TEXT NOT NULL DEFAULT 'unknown',
                agent_name TEXT,
                tool_calls TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY(actor_id) REFERENCES app_users(actor_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                meeting_request TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                final_decision TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(ai_audit_log)").fetchall()}
        if "runtime" not in columns:
            connection.execute("ALTER TABLE ai_audit_log ADD COLUMN runtime TEXT NOT NULL DEFAULT 'unknown'")
        if "agent_name" not in columns:
            connection.execute("ALTER TABLE ai_audit_log ADD COLUMN agent_name TEXT")
        if "tool_calls" not in columns:
            connection.execute("ALTER TABLE ai_audit_log ADD COLUMN tool_calls TEXT NOT NULL DEFAULT '[]'")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_created_at ON ai_audit_log(created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_actor_id ON ai_audit_log(actor_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_operation ON ai_audit_log(operation)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_runtime ON ai_audit_log(runtime)")

    def _ensure_postgres_schema(self, connection: DatabaseConnection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                recommendation_id TEXT,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                actor_id TEXT PRIMARY KEY,
                email TEXT,
                display_name TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_audit_log (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                actor_id TEXT NOT NULL REFERENCES app_users(actor_id),
                operation TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_status TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                request_payload JSONB NOT NULL,
                response_payload JSONB,
                error_code TEXT,
                error_message JSONB,
                runtime TEXT NOT NULL DEFAULT 'unknown',
                agent_name TEXT,
                tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_log (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL,
                meeting_request JSONB NOT NULL,
                recommendation JSONB NOT NULL,
                final_decision TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )
        connection.execute("ALTER TABLE ai_audit_log ADD COLUMN IF NOT EXISTS runtime TEXT NOT NULL DEFAULT 'unknown'")
        connection.execute("ALTER TABLE ai_audit_log ADD COLUMN IF NOT EXISTS agent_name TEXT")
        connection.execute("ALTER TABLE ai_audit_log ADD COLUMN IF NOT EXISTS tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_created_at ON ai_audit_log(created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_actor_id ON ai_audit_log(actor_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_operation ON ai_audit_log(operation)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_ai_audit_runtime ON ai_audit_log(runtime)")


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql://" + database_url.removeprefix("postgres://")
    return database_url
