import json
import re
from typing import Any

from pydantic import ValidationError

from app.schemas import ExpectedIntent, FieldDiff

EXACT_FIELDS = ["requester", "duration_minutes", "priority", "meeting_type", "attendees", "missing_fields", "sensitivity"]
BOOLEAN_FIELDS = ["async_candidate", "escalation_required"]
SOFT_FIELDS = ["title", "constraints", "preferred_windows"]


def parse_model_content(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Model output was not a JSON object")
    intent = value.get("intent") if isinstance(value.get("intent"), dict) else value
    return normalize_intent(intent)


def normalize_intent(value: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(value)
    normalized["title"] = _clean_string(normalized.get("title", ""))
    normalized["requester"] = _clean_string(normalized.get("requester", "Unknown requester")) or "Unknown requester"
    normalized["duration_minutes"] = _duration(normalized.get("duration_minutes") or normalized.get("duration"))
    normalized["priority"] = _enum(normalized.get("priority"), {"low", "normal", "high", "urgent"}, "normal")
    normalized["meeting_type"] = _enum(
        normalized.get("meeting_type"),
        {"intro", "internal", "customer", "investor", "candidate", "vendor", "partner", "board", "legal_hr", "personal", "other"},
        "other",
    )
    normalized["attendees"] = _clean_list(normalized.get("attendees"))
    normalized["preferred_windows"] = normalized.get("preferred_windows") if isinstance(normalized.get("preferred_windows"), list) else []
    normalized["constraints"] = _clean_list(normalized.get("constraints"))
    normalized["missing_fields"] = _clean_list(normalized.get("missing_fields"))
    normalized["sensitivity"] = _enum(normalized.get("sensitivity"), {"low", "medium", "high"}, "low")
    normalized["async_candidate"] = bool(normalized.get("async_candidate", False))
    normalized["escalation_required"] = bool(normalized.get("escalation_required", False))
    return normalized


def score_output(actual: dict[str, Any], expected: ExpectedIntent) -> tuple[bool, float, list[FieldDiff]]:
    diffs: list[FieldDiff] = []
    expected_payload = expected.model_dump(mode="json")
    for field in EXACT_FIELDS:
        expected_value = _normalized_value(field, expected_payload[field])
        actual_value = _normalized_value(field, actual.get(field))
        diffs.append(
            FieldDiff(
                field=field,
                expected=expected_payload[field],
                actual=actual.get(field),
                passed=actual_value == expected_value,
                message="" if actual_value == expected_value else "exact field mismatch",
            )
        )
    for field in BOOLEAN_FIELDS:
        expected_value = bool(expected_payload[field])
        actual_value = bool(actual.get(field, False))
        diffs.append(
            FieldDiff(
                field=field,
                expected=expected_value,
                actual=actual_value,
                passed=actual_value == expected_value,
                message="" if actual_value == expected_value else "boolean field mismatch",
            )
        )
    for field in SOFT_FIELDS:
        passed = _soft_match(field, actual.get(field), expected_payload[field])
        diffs.append(
            FieldDiff(
                field=field,
                expected=expected_payload[field],
                actual=actual.get(field),
                passed=passed,
                message="" if passed else "soft field mismatch",
            )
        )
    passed_count = sum(1 for diff in diffs if diff.passed)
    score = passed_count / len(diffs) if diffs else 0.0
    return all(diff.passed for diff in diffs), score, diffs


def validate_expected_shape(payload: dict[str, Any]) -> ExpectedIntent:
    return ExpectedIntent.model_validate(payload)


def safe_validation_error(exc: ValidationError | Exception) -> str:
    return re.sub(r"\s+", " ", str(exc)).strip()[:500]


def _duration(value: Any) -> int:
    if isinstance(value, int):
        return max(15, min(240, value))
    if isinstance(value, str):
        match = re.search(r"\d{1,3}", value)
        if match:
            return max(15, min(240, int(match.group(0))))
    return 30


def _enum(value: Any, allowed: set[str], default: str) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    return normalized if normalized in allowed else default


def _clean_string(value: Any) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n,.;:") if isinstance(value, str) else ""


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in value:
        text = _clean_string(item)
        if not text:
            continue
        key = text.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(text)
    return cleaned


def _normalized_value(field: str, value: Any) -> Any:
    if field in {"attendees", "missing_fields"}:
        return sorted(item.lower() for item in _clean_list(value))
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _soft_match(field: str, actual: Any, expected: Any) -> bool:
    if field == "title":
        expected_text = _clean_string(expected).lower()
        actual_text = _clean_string(actual).lower()
        if not expected_text:
            return True
        expected_tokens = [token for token in re.split(r"\W+", expected_text) if len(token) > 3]
        return bool(actual_text) and (expected_text in actual_text or any(token in actual_text for token in expected_tokens))
    if field == "constraints":
        expected_items = set(item.lower() for item in _clean_list(expected))
        actual_items = set(item.lower() for item in _clean_list(actual))
        return expected_items.issubset(actual_items)
    if field == "preferred_windows":
        if not expected:
            return actual in ([], None)
        return isinstance(actual, list) and len(actual) > 0
    return False
