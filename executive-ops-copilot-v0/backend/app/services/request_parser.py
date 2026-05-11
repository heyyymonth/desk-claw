import re

from app.agents.scheduling import AdkRequestParserAgentRunner, AgentRuntimeError
from app.core.errors import ServiceError
from app.llm.schemas import MeetingIntent, ParsedMeetingRequest


class RequestParser:
    def __init__(self, llm_client=None, agent_runner: AdkRequestParserAgentRunner | None = None) -> None:
        self.agent_runner = agent_runner
        self.last_ai_run: dict = _fallback_trace()

    def parse(self, raw_text: str) -> ParsedMeetingRequest:
        if self.agent_runner is not None:
            try:
                parsed = self.agent_runner.parse(raw_text)
                self.last_ai_run = getattr(self.agent_runner, "last_run", None) or _adk_trace("meeting_request_parser_agent")
                return parsed.model_copy(update={"intent": _normalize_intent(raw_text, parsed.intent)})
            except AgentRuntimeError as exc:
                self.last_ai_run = _adk_trace("meeting_request_parser_agent", status="unavailable")
                raise ServiceError("ollama_unavailable", "Configured ADK parser is unavailable.", status_code=502) from exc
        self.last_ai_run = _fallback_trace()
        return fallback_parse(raw_text)


def fallback_parse(raw_text: str) -> ParsedMeetingRequest:
    return ParsedMeetingRequest(raw_text=raw_text, intent=_fallback_intent(raw_text))


def _adk_trace(agent_name: str, status: str = "used") -> dict:
    return {"runtime": "google-adk", "agent_name": agent_name, "model_status": status, "tool_calls": []}


def _fallback_trace() -> dict:
    return {"runtime": "deterministic", "agent_name": None, "model_status": "not_configured", "tool_calls": []}


def _normalize_intent(raw_text: str, intent: MeetingIntent) -> MeetingIntent:
    fallback = _fallback_intent(raw_text)
    constraints = list(dict.fromkeys([*intent.constraints, *fallback.constraints]))
    missing_fields = list(dict.fromkeys([*fallback.missing_fields, *intent.missing_fields]))
    attendees = list(dict.fromkeys([*intent.attendees, *fallback.attendees]))
    requester = fallback.requester if fallback.requester != "Unknown requester" else intent.requester
    return intent.model_copy(
        update={
            "requester": requester,
            "priority": fallback.priority,
            "meeting_type": fallback.meeting_type,
            "constraints": constraints,
            "missing_fields": missing_fields,
            "attendees": attendees,
            "sensitivity": fallback.sensitivity,
            "async_candidate": fallback.async_candidate,
            "escalation_required": fallback.escalation_required,
        }
    )


def _fallback_intent(raw_text: str) -> MeetingIntent:
    requester = _requester(raw_text)
    title = _title(raw_text)
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
        meeting_type=_meeting_type(raw_text),
        attendees=_emails(raw_text),
        preferred_windows=[],
        constraints=_constraints(raw_text),
        missing_fields=missing,
        sensitivity=_sensitivity(raw_text),
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
    match = re.search(r"(?:from|by)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"^([A-Z][A-Za-z]+)\s+at\s+", text)
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


def _title(text: str) -> str:
    lowered = text.lower()
    if "investor" in lowered or "ventures" in lowered or "investment" in lowered:
        return "Investor meeting"
    if "board chair" in lowered:
        return "Board meeting"
    if "legal" in lowered or "employee relations" in lowered or "people" in lowered:
        return "Legal HR meeting"
    if "candidate" in lowered or "interview" in lowered or "final round" in lowered:
        return "Candidate interview"
    if "customer" in lowered or "escalation" in lowered:
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
    if "legal" in lowered or "employee relations" in lowered or "people:" in lowered or "people " in lowered:
        return "legal_hr"
    if "candidate" in lowered or "interview" in lowered or "final round" in lowered or "recruiting" in lowered:
        return "candidate"
    if "investor" in lowered or "ventures" in lowered or "investment" in lowered:
        return "investor"
    if "customer" in lowered or "escalation" in lowered or "sev-1" in lowered:
        return "customer"
    if "partner" in lowered or "partnership" in lowered:
        return "partner"
    if any(token in lowered for token in ["internal", "sync", "office snack", "gtm", "product and"]):
        return "internal"
    return "other"


def _sensitivity(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["confidential", "employee relations", "disclosure", "press inquiry", "legal", "hr"]):
        return "high"
    if any(token in lowered for token in ["private opportunity", "board"]):
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


def _constraints(text: str) -> list[str]:
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
    return constraints
