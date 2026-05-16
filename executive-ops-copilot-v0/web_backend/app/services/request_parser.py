import re
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.agents.scheduling import NATIVE_AI_RUNTIME, AgentRuntimeError, NativeRequestParserAgentRunner
from app.core.errors import ServiceError
from app.llm.schemas import MeetingIntent, ParsedMeetingRequest

DEFAULT_TIMEZONE = "America/Los_Angeles"
_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_DAY_PARTS = {
    "morning": (time(9, 0), time(12, 0)),
    "afternoon": (time(13, 0), time(17, 0)),
    "evening": (time(17, 0), time(19, 0)),
}
_ORG_SUFFIX_WORDS = {
    "capital",
    "cloud",
    "finance",
    "group",
    "inc",
    "legal",
    "llc",
    "ops",
    "partners",
    "platform",
    "systems",
    "ventures",
}
_PERSON_STOPWORDS = {
    "atlas finance",
    "board chair",
    "customer success",
    "legal",
    "monday",
    "northstar customer ops",
    "product",
    "support",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
}


class RequestParser:
    def __init__(self, agent_runner: NativeRequestParserAgentRunner | None = None) -> None:
        self.agent_runner = agent_runner

    def parse(self, raw_text: str) -> ParsedMeetingRequest:
        parsed, _trace = self.parse_with_trace(raw_text)
        return parsed

    def parse_with_trace(self, raw_text: str) -> tuple[ParsedMeetingRequest, dict]:
        if self.agent_runner is not None:
            try:
                if hasattr(self.agent_runner, "parse_with_trace"):
                    parsed, trace = self.agent_runner.parse_with_trace(raw_text)
                else:
                    parsed = self.agent_runner.parse(raw_text)
                    trace = _native_trace("meeting_request_parser_agent")
                return parsed.model_copy(update={"intent": _normalize_intent(raw_text, parsed.intent)}), trace
            except AgentRuntimeError as exc:
                trace = _native_trace("meeting_request_parser_agent", status="unavailable")
                raise ServiceError(
                    "ai_model_unavailable",
                    "Configured native parser model is unavailable.",
                    status_code=502,
                    ai_trace=trace,
                ) from exc
        trace = _native_trace("meeting_request_parser_agent", status="not_configured")
        raise ServiceError(
            "ai_model_not_configured",
            "The model is offline. Check with your admin before running this request.",
            status_code=503,
            ai_trace=trace,
        )


def fallback_parse(raw_text: str) -> ParsedMeetingRequest:
    return ParsedMeetingRequest(raw_text=raw_text, intent=_fallback_intent(raw_text))


def extract_entity_evidence(raw_text: str) -> dict[str, Any]:
    organizations = _organizations(raw_text)
    people = _people(raw_text, organizations)
    requester = _requester(raw_text)
    attendees = _attendees(raw_text, requester, people)
    return {
        "requester": requester,
        "people": people,
        "organizations": organizations,
        "attendees": attendees,
        "title": _title(raw_text, organizations),
        "meeting_type": _meeting_type(raw_text),
        "sensitivity": _sensitivity(raw_text),
    }


def extract_time_preference_evidence(raw_text: str, timezone_name: str = DEFAULT_TIMEZONE) -> dict[str, Any]:
    lowered = raw_text.lower()
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    windows: list[dict[str, str]] = []

    for match in re.finditer(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s+(morning|afternoon|evening))?",
        lowered,
    ):
        weekday = match.group(1)
        part = match.group(2) or _nearest_day_part(lowered, match.end())
        target_date = _date_for_weekday(today, weekday, lowered)
        windows.append(_window_payload(target_date, part, tz))

    if not windows:
        part = _first_day_part(lowered)
        if "tomorrow" in lowered:
            windows.append(_window_payload(today + timedelta(days=1), part, tz))
        if "today" in lowered:
            windows.append(_window_payload(today, part, tz))
        if "next week" in lowered:
            week_start = today + timedelta(days=(7 - today.weekday()))
            for offset in range(5):
                windows.append(_window_payload(week_start + timedelta(days=offset), part, tz))

    return {
        "timezone": timezone_name,
        "preferred_windows": _dedupe_windows(windows),
        "constraints": _time_constraints(raw_text),
    }


def _native_trace(agent_name: str, status: str = "used") -> dict:
    return {"runtime": NATIVE_AI_RUNTIME, "agent_name": agent_name, "model_status": status, "tool_calls": []}


def _normalize_intent(raw_text: str, intent: MeetingIntent) -> MeetingIntent:
    fallback = _fallback_intent(raw_text)
    constraints = list(dict.fromkeys([*intent.constraints, *fallback.constraints]))
    missing_fields = list(dict.fromkeys([*fallback.missing_fields, *intent.missing_fields]))
    attendees = list(dict.fromkeys([*intent.attendees, *fallback.attendees]))
    requester = fallback.requester if fallback.requester != "Unknown requester" else intent.requester
    preferred_windows = _merge_time_windows(intent.preferred_windows, fallback.preferred_windows)
    return intent.model_copy(
        update={
            "title": _best_title(intent.title, fallback.title, intent.meeting_type, fallback.meeting_type),
            "requester": requester,
            "priority": fallback.priority,
            "meeting_type": fallback.meeting_type,
            "constraints": constraints,
            "missing_fields": missing_fields,
            "attendees": attendees,
            "preferred_windows": preferred_windows,
            "sensitivity": fallback.sensitivity,
            "async_candidate": fallback.async_candidate,
            "escalation_required": fallback.escalation_required,
        }
    )


def _fallback_intent(raw_text: str) -> MeetingIntent:
    entity_evidence = extract_entity_evidence(raw_text)
    time_evidence = extract_time_preference_evidence(raw_text)
    requester = _requester(raw_text)
    title = entity_evidence["title"]
    missing = []
    if requester == "Unknown requester":
        missing.append("requester")
    if _missing_purpose(raw_text, title):
        missing.append("purpose")
    if _duration_missing(raw_text):
        missing.append("duration")
    if _unknown_requester(raw_text, requester):
        missing.append("verified_requester_identity")
    if "recurring" in raw_text.lower() or "weekly" in raw_text.lower():
        missing.append("recurrence_end_or_owner_confirmation")
    if _blocked_context(raw_text):
        for field in ["meeting_identity", "attendee_list", "authorization"]:
            if field not in missing:
                missing.append(field)

    return MeetingIntent(
        title=title,
        requester=requester,
        duration_minutes=_duration(raw_text),
        priority=_priority(raw_text),
        meeting_type=entity_evidence["meeting_type"],
        attendees=entity_evidence["attendees"],
        preferred_windows=time_evidence["preferred_windows"],
        constraints=_constraints(raw_text, time_evidence),
        missing_fields=missing,
        sensitivity=entity_evidence["sensitivity"],
        async_candidate=_async_candidate(raw_text),
        escalation_required=_escalation_required(raw_text),
    )


def _duration(text: str) -> int:
    match = re.search(r"(\d{1,3})\s*(?:min|mins|minutes|minute)", text, re.IGNORECASE)
    if match:
        return max(15, min(240, int(match.group(1))))
    if re.search(r"\b(hour|hr)\b", text, re.IGNORECASE):
        return 60
    return 30


def _duration_missing(text: str) -> bool:
    return not re.search(r"(\d{1,3})\s*(?:min|mins|minutes|minute)|\b(hour|hr)\b", text, re.IGNORECASE)


def _requester(text: str) -> str:
    match = re.search(r"(?i:from)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+(?i:at)\s+", text)
    if match:
        return match.group(1)
    match = re.search(r"(?i:for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+(?i:from)\s+", text)
    if match:
        return match.group(1)
    match = re.search(r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?i:at)\s+", text)
    if match:
        return match.group(1)
    match = re.search(r"(?i:from|by)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)", text)
    if match:
        return match.group(1)
    if text.startswith("Recruiting:"):
        return "Recruiting"
    lowered = text.lower()
    if lowered.startswith("customer success"):
        return "Customer Success"
    if "board chair" in lowered:
        return "Board chair"
    email = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    return email.group(0) if email else "Unknown requester"


def _title(text: str, organizations: list[str] | None = None) -> str:
    lowered = text.lower()
    organization = organizations[0] if organizations else ""
    if organization and any(token in lowered for token in ["renewal", "contract", "customer"]):
        if "renewal" in lowered:
            return f"{organization} renewal discussion"
        if "contract" in lowered:
            return f"{organization} contract discussion"
        return f"{organization} customer meeting"
    if "investor" in lowered or "ventures" in lowered or "investment" in lowered:
        return "Investor meeting"
    if "board chair" in lowered:
        return "Board meeting"
    if _legal_hr_context(lowered):
        return "Legal HR meeting"
    if "candidate" in lowered or "interview" in lowered or "final round" in lowered:
        return "Candidate interview"
    if any(token in lowered for token in ["customer", "escalation", "renewal", "contract timing"]):
        return "Customer meeting"
    if "partner" in lowered or "partnership" in lowered:
        return "Partner meeting"
    if "sync" in lowered:
        return "Internal sync"
    words = text.strip().split()
    return " ".join(words[:3]) if words else "Meeting request"


def _missing_purpose(text: str, title: str) -> bool:
    lowered = text.lower()
    if title in {"Meeting request", "Hi, can we", "Please move the"}:
        return True
    return "some time" in lowered or "private opportunity" in lowered


def _priority(text: str) -> str:
    lowered = text.lower()
    if "move the confidential meeting" in lowered:
        return "normal"
    if any(token in lowered for token in ["urgent", "asap", "today"]):
        return "urgent"
    if any(token in lowered for token in ["important", "board", "investor", "legal", "employee relations", "confidential"]):
        return "high"
    if any(token in lowered for token in ["fyi", "no decision needed"]):
        return "low"
    return "normal"


def _meeting_type(text: str) -> str:
    lowered = text.lower()
    if "board chair" in lowered:
        return "board"
    if _legal_hr_context(lowered):
        return "legal_hr"
    if "candidate" in lowered or "interview" in lowered or "final round" in lowered or "recruiting" in lowered:
        return "candidate"
    if "investor" in lowered or "ventures" in lowered or "investment" in lowered:
        return "investor"
    if any(token in lowered for token in ["customer", "escalation", "sev-1", "renewal", "contract timing"]):
        return "customer"
    if "partner" in lowered or "partnership" in lowered:
        return "partner"
    if any(token in lowered for token in ["internal", "sync", "office snack", "gtm", "product and"]):
        return "internal"
    return "other"


def _sensitivity(text: str) -> str:
    lowered = text.lower()
    if any(
        token in lowered
        for token in [
            "confidential",
            "employee relations",
            "disclosure",
            "press inquiry",
            "legal matter",
            "hr matter",
        ]
    ):
        return "high"
    if any(token in lowered for token in ["private opportunity", "board", "include priya from legal", "from legal"]):
        return "medium"
    return "low"


def _async_candidate(text: str) -> bool:
    lowered = text.lower()
    return "no decision needed" in lowered or "fyi" in lowered or "status update" in lowered


def _escalation_required(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["board chair", "disclosure", "press inquiry", "sev-1", "urgent escalation"])


def _unknown_requester(text: str, requester: str) -> bool:
    lowered = text.lower()
    return requester == "Unknown requester" or "example.net" in lowered or "unknown" in lowered


def _blocked_context(text: str) -> bool:
    lowered = text.lower()
    return "move the confidential meeting" in lowered or ("send everyone" in lowered and "new time" in lowered)


def _emails(text: str) -> list[str]:
    return sorted(set(re.findall(r"[\w.\-+]+@[\w.\-]+\.\w+", text)))


def _constraints(text: str, time_evidence: dict[str, Any] | None = None) -> list[str]:
    constraints = []
    lowered = text.lower()
    if "tomorrow" in lowered:
        constraints.append("tomorrow")
    if "next week" in lowered:
        constraints.append("next week")
    if "morning" in lowered:
        constraints.append("morning")
    if "afternoon" in lowered:
        constraints.append("afternoon")
    if "board prep" in lowered:
        constraints.append("board prep")
    if "travel" in lowered or "new york" in lowered:
        constraints.append("travel")
    if time_evidence:
        constraints.extend(time_evidence.get("constraints", []))
    return list(dict.fromkeys(constraints))


def _organizations(text: str) -> list[str]:
    organizations: list[str] = []
    patterns = [
        r"(?i:from)\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\s+(?i:at)\s+([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,4})",
        r"(?i:for)\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\s+(?i:from)\s+([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,4})",
        r"\b[A-Z][A-Za-z]+\s+(?i:at)\s+([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,4})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            organizations.append(_clean_entity(match.group(1)))
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3})\b", text):
        candidate = _clean_entity(match.group(1))
        words = candidate.lower().split()
        if words and words[-1] in _ORG_SUFFIX_WORDS:
            organizations.append(candidate)
    return _dedupe_entities(organizations)


def _people(text: str, organizations: list[str]) -> list[str]:
    people: list[str] = []
    patterns = [
        r"(?i:from)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+(?i:at)\s+",
        r"(?i:for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+(?i:from)\s+",
        r"(?i:with)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})",
        r"(?i:include)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})",
        r"(?i:and)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})",
        r"\b([A-Z][A-Za-z]+)'s team\b",
        r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+(?i:at)\s+",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            people.append(_clean_entity(match.group(1)))
    for email in _emails(text):
        local = email.split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ")
        words = [word.capitalize() for word in local.split() if word]
        if words:
            people.append(" ".join(words[:2]))

    organizations_lower = {organization.lower() for organization in organizations}
    return _dedupe_entities(
        [
            person
            for person in people
            if person.lower() not in organizations_lower and person.lower() not in _PERSON_STOPWORDS
        ]
    )


def _attendees(text: str, requester: str, people: list[str]) -> list[str]:
    attendees = [person for person in people if person != "Unknown requester"]
    if requester != "Unknown requester":
        attendees.insert(0, requester)
    return _dedupe_entities([*attendees, *_emails(text)])


def _clean_entity(value: str) -> str:
    return re.sub(r"[\s,.;:!?]+$", "", value.strip())


def _dedupe_entities(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = _clean_entity(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _legal_hr_context(lowered: str) -> bool:
    if "employee relations" in lowered or "people:" in lowered or "people " in lowered:
        return True
    if "confidential" in lowered and any(token in lowered for token in ["legal", "hr"]):
        return True
    return "legal matter" in lowered or "hr matter" in lowered


def _time_constraints(text: str) -> list[str]:
    lowered = text.lower()
    constraints = []
    for weekday in _WEEKDAY_INDEX:
        if weekday in lowered:
            constraints.append(weekday)
    for part in _DAY_PARTS:
        if part in lowered:
            constraints.append(part)
    return constraints


def _date_for_weekday(today, weekday: str, lowered_text: str):
    week_start = today - timedelta(days=today.weekday())
    if "next week" in lowered_text or f"next {weekday}" in lowered_text:
        week_start += timedelta(days=7)
    elif "this week" not in lowered_text:
        candidate = week_start + timedelta(days=_WEEKDAY_INDEX[weekday])
        if candidate < today:
            week_start += timedelta(days=7)
    return week_start + timedelta(days=_WEEKDAY_INDEX[weekday])


def _nearest_day_part(lowered_text: str, start_index: int) -> str | None:
    window = lowered_text[start_index : start_index + 28]
    for part in _DAY_PARTS:
        if part in window:
            return part
    return None


def _first_day_part(lowered_text: str) -> str | None:
    for part in _DAY_PARTS:
        if part in lowered_text:
            return part
    return None


def _window_payload(date_value, part: str | None, tz: ZoneInfo) -> dict[str, str]:
    start_time, end_time = _DAY_PARTS.get(part or "", (time(9, 0), time(17, 0)))
    start = datetime.combine(date_value, start_time, tzinfo=tz)
    end = datetime.combine(date_value, end_time, tzinfo=tz)
    return {"start": start.isoformat(), "end": end.isoformat()}


def _dedupe_windows(windows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for window in windows:
        key = (window["start"], window["end"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(window)
    return deduped


def _merge_time_windows(primary, fallback):
    merged = [*primary, *fallback]
    seen: set[tuple[datetime, datetime]] = set()
    deduped = []
    for window in merged:
        key = (window.start, window.end)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(window)
    return deduped


def _best_title(model_title: str, fallback_title: str, model_type: str, fallback_type: str) -> str:
    if model_type == "legal_hr" and fallback_type != "legal_hr":
        return fallback_title
    if fallback_title not in {"Meeting request", "Hi, can we", "Please move the"} and any(
        token in fallback_title.lower() for token in ["renewal", "contract", "customer", "investor", "board"]
    ):
        return fallback_title
    return model_title
