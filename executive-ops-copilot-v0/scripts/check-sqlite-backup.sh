#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: check-sqlite-backup.sh <sqlite-backup.db[.gz]> [expected-row-counts-file]

Validates a Desk AI SQLite backup artifact before storing or restoring it.

Environment:
  EXPECTED_TABLES="decisions app_users ai_audit_log decision_log"
  MIN_TOTAL_ROWS=0
  ROW_COUNTS_OUTPUT=<optional output file>
  PYTHON=python3
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

BACKUP_PATH="$1"
EXPECTED_ROW_COUNTS_FILE="${2:-}"
EXPECTED_TABLES="${EXPECTED_TABLES:-decisions app_users ai_audit_log decision_log}"
MIN_TOTAL_ROWS="${MIN_TOTAL_ROWS:-0}"
ROW_COUNTS_OUTPUT="${ROW_COUNTS_OUTPUT:-}"
PYTHON="${PYTHON:-python3}"

if [[ ! -f "$BACKUP_PATH" ]]; then
  echo "SQLite backup file does not exist: $BACKUP_PATH" >&2
  exit 1
fi

if [[ -n "$EXPECTED_ROW_COUNTS_FILE" && ! -f "$EXPECTED_ROW_COUNTS_FILE" ]]; then
  echo "Expected row-count file does not exist: $EXPECTED_ROW_COUNTS_FILE" >&2
  exit 1
fi

if [[ -n "$ROW_COUNTS_OUTPUT" ]]; then
  mkdir -p "$(dirname "$ROW_COUNTS_OUTPUT")"
fi

case "$MIN_TOTAL_ROWS" in
  ''|*[!0-9]*)
    echo "MIN_TOTAL_ROWS must be a non-negative integer." >&2
    exit 1
    ;;
esac

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Required command is not available: $PYTHON" >&2
  exit 1
fi

export EXPECTED_TABLES MIN_TOTAL_ROWS

"$PYTHON" - "$BACKUP_PATH" "$EXPECTED_ROW_COUNTS_FILE" "$ROW_COUNTS_OUTPUT" <<'PY'
from __future__ import annotations

import gzip
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


backup_path = Path(sys.argv[1])
expected_counts_path = Path(sys.argv[2]) if sys.argv[2] else None
row_counts_output = Path(sys.argv[3]) if sys.argv[3] else None
expected_tables = os.environ["EXPECTED_TABLES"].split()
min_total_rows = int(os.environ["MIN_TOTAL_ROWS"])
identifier_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def is_gzip(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(2) == b"\x1f\x8b"


def parse_row_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            fail(f"{path}:{line_number} must use table=count format.")
        table, raw_count = line.split("=", 1)
        table = table.strip()
        raw_count = raw_count.strip()
        if not table or not raw_count.isdigit():
            fail(f"{path}:{line_number} must use table=count format with a non-negative integer count.")
        if not identifier_pattern.match(table):
            fail(f"{path}:{line_number} contains invalid table name {table!r}.")
        counts[table] = int(raw_count)
    return counts


if backup_path.stat().st_size == 0:
    fail(f"SQLite backup file is empty: {backup_path}")

invalid_tables = [table for table in expected_tables if not identifier_pattern.match(table)]
if invalid_tables:
    fail(f"EXPECTED_TABLES contains invalid table name(s): {', '.join(invalid_tables)}")

temp_path: str | None = None
try:
    if is_gzip(backup_path):
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            with gzip.open(backup_path, "rb") as source:
                shutil.copyfileobj(source, temp_file)
        db_path = Path(temp_path)
    else:
        db_path = backup_path

    if db_path.stat().st_size == 0:
        fail(f"SQLite backup payload is empty after decompression: {backup_path}")

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            fail(f"SQLite integrity_check failed for {backup_path}: {integrity}")

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        missing = sorted(set(expected_tables) - tables)
        if missing:
            fail(f"SQLite backup is missing required table(s): {', '.join(missing)}")

        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in expected_tables
        }
    finally:
        connection.close()

    total_rows = sum(counts.values())
    if total_rows < min_total_rows:
        fail(f"SQLite backup has {total_rows} total row(s), expected at least {min_total_rows}.")

    if expected_counts_path:
        expected_counts = parse_row_counts(expected_counts_path)
        unknown_tables = sorted(set(expected_counts) - tables)
        if unknown_tables:
            fail(f"Row-count file references unknown table(s): {', '.join(unknown_tables)}")
        mismatches = [
            f"{table}: backup={counts.get(table, 0)} expected={expected_count}"
            for table, expected_count in expected_counts.items()
            if counts.get(table, 0) != expected_count
        ]
        if mismatches:
            fail("SQLite backup row-count mismatch: " + "; ".join(mismatches))

    if row_counts_output:
        row_counts_output.write_text(
            "".join(f"{table}={counts[table]}\n" for table in expected_tables),
            encoding="utf-8",
        )

    print(f"SQLite backup check passed for {backup_path}.")
    print(f"Required tables: {', '.join(expected_tables)}.")
    print(f"Total rows across required tables: {total_rows}.")
    for table in expected_tables:
        print(f"{table}={counts[table]}")
finally:
    if temp_path:
        Path(temp_path).unlink(missing_ok=True)
PY
