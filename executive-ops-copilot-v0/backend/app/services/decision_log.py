from app.db.session import Database
from app.llm.schemas import DecisionFeedback, DecisionLogEntry


class DecisionLogService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def log(self, feedback: DecisionFeedback) -> DecisionLogEntry:
        entry = DecisionLogEntry(**feedback.model_dump())
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO decisions (id, action, recommendation_id, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entry.id, entry.action, entry.recommendation_id, entry.notes, entry.created_at.isoformat()),
            )
            connection.commit()
        return entry

    def list(self) -> list[DecisionLogEntry]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id, action, recommendation_id, notes, created_at FROM decisions ORDER BY created_at DESC"
            ).fetchall()
        return [DecisionLogEntry.model_validate(dict(row)) for row in rows]
