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
        connection.commit()
