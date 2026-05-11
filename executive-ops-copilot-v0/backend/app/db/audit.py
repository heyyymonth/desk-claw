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

    def ai_metrics(self, limit: int = 250) -> dict[str, Any]:
        events = self.list_ai_events(limit)
        total = len(events)
        if total == 0:
            return {
                "total_events": 0,
                "success_rate": 0.0,
                "adk_coverage": 0.0,
                "tool_call_coverage": 0.0,
                "avg_latency_ms": 0,
                "p95_latency_ms": 0,
                "model_status_counts": {},
                "operation_metrics": [],
                "slowest_events": [],
                "recent_failures": [],
            }

        successful = [event for event in events if event["status"] == "success"]
        adk_events = [event for event in events if event["runtime"] == "google-adk"]
        tool_events = [event for event in adk_events if event["tool_calls"]]
        latencies = sorted(int(event["latency_ms"]) for event in events)
        operations = sorted({event["operation"] for event in events})

        return {
            "total_events": total,
            "success_rate": round(len(successful) / total, 3),
            "adk_coverage": round(len(adk_events) / total, 3),
            "tool_call_coverage": round(len(tool_events) / max(1, len(adk_events)), 3),
            "avg_latency_ms": round(sum(latencies) / total),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "model_status_counts": _counts(event["model_status"] for event in events),
            "operation_metrics": [_operation_metric(operation, events) for operation in operations],
            "slowest_events": [
                _event_summary(event)
                for event in sorted(events, key=lambda row: int(row["latency_ms"]), reverse=True)[:5]
            ],
            "recent_failures": [
                _event_summary(event)
                for event in events
                if event["status"] != "success" or event["model_status"] in {"unavailable", "invalid_output"}
            ][:5],
        }


def _to_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, default=str)


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, round((len(values) - 1) * percentile))
    return values[index]


def _operation_metric(operation: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [event for event in events if event["operation"] == operation]
    latencies = [int(event["latency_ms"]) for event in rows]
    adk_rows = [event for event in rows if event["runtime"] == "google-adk"]
    return {
        "operation": operation,
        "total": len(rows),
        "success_rate": round(sum(1 for event in rows if event["status"] == "success") / len(rows), 3),
        "adk_coverage": round(len(adk_rows) / len(rows), 3),
        "avg_latency_ms": round(sum(latencies) / len(latencies)),
        "tool_calls_avg": round(sum(len(event["tool_calls"]) for event in rows) / len(rows), 2),
        "model_status_counts": _counts(event["model_status"] for event in rows),
    }


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "created_at": event["created_at"],
        "operation": event["operation"],
        "model_name": event["model_name"],
        "model_status": event["model_status"],
        "runtime": event["runtime"],
        "agent_name": event["agent_name"],
        "latency_ms": event["latency_ms"],
        "status": event["status"],
        "error_code": event["error_code"],
        "tool_calls": event["tool_calls"],
    }
