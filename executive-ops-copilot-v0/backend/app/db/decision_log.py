import json
from datetime import datetime, timezone
from typing import Any

from app.db.session import Database
from app.models import DecisionLogEntry, DecisionLogInput


class DecisionLogRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, entry: DecisionLogInput) -> DecisionLogEntry:
        created_at = datetime.now(timezone.utc)
        meeting_request = _to_db_json(self.database, entry.meeting_request.model_dump(mode="json"))
        recommendation = _to_db_json(self.database, entry.recommendation.model_dump(mode="json"))
        with self.database.connect() as connection:
            if self.database.dialect == "postgres":
                row = connection.execute(
                    """
                    INSERT INTO decision_log (created_at, meeting_request, recommendation, final_decision, notes)
                    VALUES (?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (
                        created_at,
                        meeting_request,
                        recommendation,
                        entry.final_decision,
                        entry.notes,
                    ),
                ).fetchone()
                row_id = int(row["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO decision_log (created_at, meeting_request, recommendation, final_decision, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        created_at.isoformat(),
                        meeting_request,
                        recommendation,
                        entry.final_decision,
                        entry.notes,
                    ),
                )
                row_id = int(cursor.lastrowid)
        return DecisionLogEntry(id=row_id, created_at=created_at, **entry.model_dump())

    def list(self) -> list[DecisionLogEntry]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id, created_at, meeting_request, recommendation, final_decision, notes FROM decision_log ORDER BY id DESC"
            ).fetchall()

        entries = []
        for row in rows:
            entries.append(
                DecisionLogEntry(
                    id=int(row["id"]),
                    created_at=_parse_datetime(row["created_at"]),
                    meeting_request=_from_json_or_value(row["meeting_request"]),
                    recommendation=_from_json_or_value(row["recommendation"]),
                    final_decision=row["final_decision"],
                    notes=row["notes"],
                )
            )
        return entries


def _to_db_json(database: Database, value: Any) -> Any:
    if database.dialect == "postgres":
        return database.json_value(value)
    return json.dumps(value, default=str)


def _from_json_or_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
