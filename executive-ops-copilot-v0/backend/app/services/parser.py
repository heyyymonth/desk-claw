import re

from app.models import MeetingIntent, MeetingRequest, Priority


def parse_meeting_request(raw_text: str) -> MeetingRequest:
    return MeetingRequest(raw_text=raw_text, intent=_deterministic_intent(raw_text))


def _deterministic_intent(raw_text: str) -> MeetingIntent:
    duration = _duration(raw_text)
    requester = _requester(raw_text)
    title = _title(raw_text)
    missing = []
    if requester == "Unknown requester":
        missing.append("requester")
    if "?" in title or title == "Meeting request":
        missing.append("purpose")

    return MeetingIntent(
        title=title,
        requester=requester,
        duration_minutes=duration,
        priority=_priority(raw_text),
        attendees=_emails(raw_text),
        constraints=_constraints(raw_text),
        missing_fields=missing,
    )


def _duration(text: str) -> int:
    match = re.search(r"(\d{2,3})\s*(?:min|minutes)", text, re.IGNORECASE)
    if match:
        return max(15, min(240, int(match.group(1))))
    if re.search(r"\b(hour|hr)\b", text, re.IGNORECASE):
        return 60
    return 30


def _requester(text: str) -> str:
    match = re.search(r"(?:from|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    if match:
        return match.group(1)
    email = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    return email.group(0) if email else "Unknown requester"


def _title(text: str) -> str:
    lowered = text.lower()
    if "investor" in lowered:
        return "Investor meeting"
    if "customer" in lowered:
        return "Customer meeting"
    if "interview" in lowered:
        return "Interview"
    return "Meeting request"


def _priority(text: str) -> Priority:
    lowered = text.lower()
    if any(token in lowered for token in ["urgent", "asap", "today"]):
        return Priority.urgent
    if any(token in lowered for token in ["important", "board", "investor"]):
        return Priority.high
    return Priority.normal


def _emails(text: str) -> list[str]:
    return sorted(set(re.findall(r"[\w.\-+]+@[\w.\-]+\.\w+", text)))


def _constraints(text: str) -> list[str]:
    constraints = []
    lowered = text.lower()
    if "next week" in lowered:
        constraints.append("Requested for next week")
    if "morning" in lowered:
        constraints.append("Prefers morning")
    if "afternoon" in lowered:
        constraints.append("Prefers afternoon")
    return constraints

