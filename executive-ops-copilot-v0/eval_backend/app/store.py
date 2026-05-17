import json
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import EvalCase, EvalCaseCreate, EvalCaseResult, EvalRunDetail, EvalRunSummary, ExpectedIntent, FieldDiff


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class EvalStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS eval_cases (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  description TEXT NOT NULL,
                  prompt TEXT NOT NULL,
                  expected_json TEXT NOT NULL,
                  active INTEGER NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS eval_runs (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  total_cases INTEGER NOT NULL,
                  passed_cases INTEGER NOT NULL,
                  pass_rate REAL NOT NULL,
                  avg_latency_ms REAL
                );

                CREATE TABLE IF NOT EXISTS eval_results (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  case_id TEXT NOT NULL,
                  case_name TEXT NOT NULL,
                  status TEXT NOT NULL,
                  passed INTEGER NOT NULL,
                  score REAL NOT NULL,
                  latency_ms INTEGER,
                  provider TEXT,
                  model TEXT,
                  raw_output TEXT NOT NULL,
                  normalized_json TEXT,
                  expected_json TEXT NOT NULL,
                  diffs_json TEXT NOT NULL,
                  error TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES eval_runs(id)
                );
                """
            )

    def seed_cases(self, cases: Iterable[EvalCaseCreate]) -> None:
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS count FROM eval_cases").fetchone()["count"]
            if count:
                return
            now = utc_now()
            for case in cases:
                conn.execute(
                    """
                    INSERT INTO eval_cases (id, name, description, prompt, expected_json, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        case.name,
                        case.description,
                        case.prompt,
                        case.expected.model_dump_json(),
                        int(case.active),
                        now,
                        now,
                    ),
                )

    def list_cases(self) -> list[EvalCase]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM eval_cases ORDER BY created_at ASC").fetchall()
        return [_case_from_row(row) for row in rows]

    def get_case(self, case_id: str) -> EvalCase | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM eval_cases WHERE id = ?", (case_id,)).fetchone()
        return _case_from_row(row) if row else None

    def create_case(self, case: EvalCaseCreate) -> EvalCase:
        case_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO eval_cases (id, name, description, prompt, expected_json, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (case_id, case.name, case.description, case.prompt, case.expected.model_dump_json(), int(case.active), now, now),
            )
        created = self.get_case(case_id)
        assert created is not None
        return created

    def update_case(self, case_id: str, case: EvalCaseCreate) -> EvalCase | None:
        now = utc_now()
        with self.connect() as conn:
            result = conn.execute(
                """
                UPDATE eval_cases
                SET name = ?, description = ?, prompt = ?, expected_json = ?, active = ?, updated_at = ?
                WHERE id = ?
                """,
                (case.name, case.description, case.prompt, case.expected.model_dump_json(), int(case.active), now, case_id),
            )
        return self.get_case(case_id) if result.rowcount else None

    def delete_case(self, case_id: str) -> bool:
        with self.connect() as conn:
            result = conn.execute("DELETE FROM eval_cases WHERE id = ?", (case_id,))
        return bool(result.rowcount)

    def create_run(self, results: list[EvalCaseResult]) -> EvalRunDetail:
        run_id = results[0].run_id if results else str(uuid.uuid4())
        created_at = utc_now()
        total = len(results)
        passed = sum(1 for result in results if result.passed)
        latencies = [result.latency_ms for result in results if result.latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else None
        pass_rate = passed / total if total else 0.0
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO eval_runs (id, created_at, total_cases, passed_cases, pass_rate, avg_latency_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, created_at, total, passed, pass_rate, avg_latency),
            )
            for result in results:
                conn.execute(
                    """
                    INSERT INTO eval_results (
                      id, run_id, case_id, case_name, status, passed, score, latency_ms, provider, model,
                      raw_output, normalized_json, expected_json, diffs_json, error, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.id,
                        result.run_id,
                        result.case_id,
                        result.case_name,
                        result.status,
                        int(result.passed),
                        result.score,
                        result.latency_ms,
                        result.provider,
                        result.model,
                        result.raw_output,
                        json.dumps(result.normalized_output) if result.normalized_output is not None else None,
                        result.expected.model_dump_json(),
                        json.dumps([diff.model_dump(mode="json") for diff in result.diffs]),
                        result.error,
                        result.created_at.isoformat(),
                    ),
                )
        run = self.get_run(run_id)
        assert run is not None
        return run

    def list_runs(self) -> list[EvalRunSummary]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM eval_runs ORDER BY created_at DESC").fetchall()
        return [_run_summary_from_row(row) for row in rows]

    def get_run(self, run_id: str) -> EvalRunDetail | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            result_rows = conn.execute("SELECT * FROM eval_results WHERE run_id = ? ORDER BY created_at ASC", (run_id,)).fetchall()
        summary = _run_summary_from_row(row)
        return EvalRunDetail(**summary.model_dump(), results=[_result_from_row(result_row) for result_row in result_rows])


def _case_from_row(row: sqlite3.Row) -> EvalCase:
    return EvalCase(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        prompt=row["prompt"],
        expected=ExpectedIntent.model_validate_json(row["expected_json"]),
        active=bool(row["active"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _run_summary_from_row(row: sqlite3.Row) -> EvalRunSummary:
    return EvalRunSummary(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        total_cases=row["total_cases"],
        passed_cases=row["passed_cases"],
        pass_rate=row["pass_rate"],
        avg_latency_ms=row["avg_latency_ms"],
    )


def _result_from_row(row: sqlite3.Row) -> EvalCaseResult:
    return EvalCaseResult(
        id=row["id"],
        run_id=row["run_id"],
        case_id=row["case_id"],
        case_name=row["case_name"],
        status=row["status"],
        passed=bool(row["passed"]),
        score=row["score"],
        latency_ms=row["latency_ms"],
        provider=row["provider"],
        model=row["model"],
        raw_output=row["raw_output"],
        normalized_output=json.loads(row["normalized_json"]) if row["normalized_json"] else None,
        expected=ExpectedIntent.model_validate_json(row["expected_json"]),
        diffs=[FieldDiff.model_validate(item) for item in json.loads(row["diffs_json"])],
        error=row["error"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
