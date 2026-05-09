import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from app.models import DecisionLogEntry, DecisionLogInput


class DecisionLogRepository:
    def __init__(self, sqlite_path: str) -> None:
        self.sqlite_path = sqlite_path
        self._init()

    def _connect(self) -> sqlite3.Connection:
        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True) if Path(self.sqlite_path).parent != Path(".") else None
        return sqlite3.connect(self.sqlite_path)

    def _init(self) -> None:
        with self._connect() as connection:
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

    def add(self, entry: DecisionLogInput) -> DecisionLogEntry:
        created_at = datetime.now(timezone.utc)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO decision_log (created_at, meeting_request, recommendation, final_decision, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    created_at.isoformat(),
                    entry.meeting_request.model_dump_json(),
                    entry.recommendation.model_dump_json(),
                    entry.final_decision,
                    entry.notes,
                ),
            )
            row_id = int(cursor.lastrowid)
        return DecisionLogEntry(id=row_id, created_at=created_at, **entry.model_dump())

    def list(self) -> list[DecisionLogEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, created_at, meeting_request, recommendation, final_decision, notes FROM decision_log ORDER BY id DESC"
            ).fetchall()

        entries = []
        for row in rows:
            entries.append(
                DecisionLogEntry(
                    id=row[0],
                    created_at=datetime.fromisoformat(row[1]),
                    meeting_request=json.loads(row[2]),
                    recommendation=json.loads(row[3]),
                    final_decision=row[4],
                    notes=row[5],
                )
            )
        return entries
