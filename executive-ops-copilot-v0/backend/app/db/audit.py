import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from app.db.session import Database


@dataclass(frozen=True)
class ActorContext:
    actor_id: str = "local-user"
    email: str | None = None
    display_name: str | None = "Local User"


@dataclass(frozen=True)
class AuditEvent:
    actor: ActorContext
    operation: str
    endpoint: str
    model_name: str
    model_status: str
    status: str
    latency_ms: int
    request_payload: Any
    response_payload: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    runtime: str = "unknown"
    agent_name: str | None = None
    tool_calls: list[str] | None = None


class AuditRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_user(self, actor: ActorContext) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO app_users (actor_id, email, display_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(actor_id) DO UPDATE SET
                    email = excluded.email,
                    display_name = excluded.display_name,
                    updated_at = excluded.updated_at
                """,
                (actor.actor_id, actor.email, actor.display_name, now, now),
            )
            connection.commit()

    def add_ai_event(self, event: AuditEvent) -> str:
        self.upsert_user(event.actor)
        event_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_audit_log (
                    id, created_at, actor_id, operation, endpoint, model_name, model_status,
                    status, latency_ms, request_payload, response_payload, error_code, error_message,
                    runtime, agent_name, tool_calls
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    created_at,
                    event.actor.actor_id,
                    event.operation,
                    event.endpoint,
                    event.model_name,
                    event.model_status,
                    event.status,
                    event.latency_ms,
                    _to_json(event.request_payload),
                    _to_json(event.response_payload) if event.response_payload is not None else None,
                    event.error_code,
                    event.error_message,
                    event.runtime,
                    event.agent_name,
                    _to_json(event.tool_calls or []),
                ),
            )
            connection.commit()
        return event_id

    def list_ai_events(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 250))
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id, created_at, actor_id, operation, endpoint, model_name, model_status,
                    status, latency_ms, request_payload, response_payload, error_code, error_message,
                    runtime, agent_name, tool_calls
                FROM ai_audit_log
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "actor_id": row["actor_id"],
                "operation": row["operation"],
                "endpoint": row["endpoint"],
                "model_name": row["model_name"],
                "model_status": row["model_status"],
                "status": row["status"],
                "latency_ms": row["latency_ms"],
                "request_payload": json.loads(row["request_payload"]),
                "response_payload": json.loads(row["response_payload"]) if row["response_payload"] else None,
                "error_code": row["error_code"],
                "error_message": row["error_message"],
                "runtime": row["runtime"],
                "agent_name": row["agent_name"],
                "tool_calls": json.loads(row["tool_calls"] or "[]"),
            }
            for row in rows
        ]


def _to_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, default=str)
