import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from app.db.session import Database

SENSITIVE_FIELD_NAMES = {
    "attendees",
    "body",
    "display_name",
    "email",
    "final_response_text",
    "message",
    "notes",
    "raw_text",
    "requester",
    "requester_name",
    "subject",
    "user_notes",
}

AI_EVENT_READ_LIMIT = 1000


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
                    _to_db_json(self.database, _redact_payload(event.request_payload)),
                    _to_db_json(self.database, _redact_payload(event.response_payload))
                    if event.response_payload is not None
                    else None,
                    event.error_code,
                    _to_db_json(self.database, _redact_text(event.error_message)) if event.error_message else None,
                    event.runtime,
                    event.agent_name,
                    _to_db_json(self.database, event.tool_calls or []),
                ),
            )
            connection.commit()
        return event_id

    def list_ai_events(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded_limit = _bounded_limit(limit)
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
                "created_at": _to_iso_string(row["created_at"]),
                "actor_id": row["actor_id"],
                "operation": row["operation"],
                "endpoint": row["endpoint"],
                "model_name": row["model_name"],
                "model_status": row["model_status"],
                "status": row["status"],
                "latency_ms": row["latency_ms"],
                "request_payload": _from_json_or_value(row["request_payload"]),
                "response_payload": _from_json_or_value(row["response_payload"]) if row["response_payload"] else None,
                "error_code": row["error_code"],
                "error_message": _from_json_or_text(row["error_message"]),
                "runtime": row["runtime"],
                "agent_name": row["agent_name"],
                "tool_calls": _from_json_or_value(row["tool_calls"] or []),
            }
            for row in rows
        ]

    def list_ai_event_summaries(self, limit: int = 250) -> list[dict[str, Any]]:
        bounded_limit = _bounded_limit(limit)
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id, created_at, actor_id, operation, endpoint, model_name, model_status,
                    status, latency_ms, error_code, error_message, runtime, agent_name, tool_calls
                FROM ai_audit_log
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "created_at": _to_iso_string(row["created_at"]),
                "actor_id": row["actor_id"],
                "operation": row["operation"],
                "endpoint": row["endpoint"],
                "model_name": row["model_name"],
                "model_status": row["model_status"],
                "status": row["status"],
                "latency_ms": row["latency_ms"],
                "error_code": row["error_code"],
                "error_message": _from_json_or_text(row["error_message"]),
                "runtime": row["runtime"],
                "agent_name": row["agent_name"],
                "tool_calls": _from_json_or_value(row["tool_calls"] or []),
            }
            for row in rows
        ]


def _to_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(mode="json"), default=str)
    return json.dumps(value, default=str)


def _to_db_json(database: Database, value: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if database.dialect == "postgres":
        return database.json_value(value)
    return json.dumps(value, default=str)


def _bounded_limit(limit: int) -> int:
    return max(1, min(limit, AI_EVENT_READ_LIMIT))


def _from_json_or_text(value: str | None) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _from_json_or_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _to_iso_string(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _redact_payload(value: Any, field_name: str | None = None) -> Any:
    if isinstance(value, BaseModel):
        return _redact_payload(value.model_dump(mode="json"), field_name)
    if isinstance(value, dict):
        return {key: _redact_payload(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_payload(item, field_name) for item in value]
    if isinstance(value, str) and _is_sensitive_field(field_name):
        return _redact_text(value)
    return value


def _is_sensitive_field(field_name: str | None) -> bool:
    return bool(field_name and field_name.lower() in SENSITIVE_FIELD_NAMES)


def _redact_text(value: str) -> dict[str, Any]:
    return {
        "redacted": True,
        "kind": "sensitive_text",
        "length": len(value),
        "sha256": sha256(value.encode("utf-8")).hexdigest(),
    }
