import sqlite3
from pathlib import Path


class Database:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// DATABASE_URL is supported in V0")
        self.path = database_url.removeprefix("sqlite:///")

    def connect(self) -> sqlite3.Connection:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        self.ensure_schema(connection)
        return connection

    @staticmethod
    def ensure_schema(connection: sqlite3.Connection) -> None:
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
        connection.commit()
