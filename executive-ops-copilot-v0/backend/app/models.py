from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class Decision(str, Enum):
    schedule = "schedule"
    decline = "decline"
    clarify = "clarify"
    defer = "defer"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class MeetingType(str, Enum):
    intro = "intro"
    internal = "internal"
    customer = "customer"
    investor = "investor"
    candidate = "candidate"
    vendor = "vendor"
    partner = "partner"
    board = "board"
    legal_hr = "legal_hr"
    personal = "personal"
    other = "other"


class ModelStatus(str, Enum):
    used = "used"
    unavailable = "unavailable"
    invalid_output = "invalid_output"
    not_configured = "not_configured"


class Tone(str, Enum):
    concise = "concise"
    warm = "warm"
    firm = "firm"


class DraftType(str, Enum):
    accept = "accept"
    decline = "decline"
    clarify = "clarify"
    defer = "defer"


class TimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime


class MeetingIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    requester: str
    duration_minutes: int = Field(ge=15, le=240)
    priority: Priority
    meeting_type: MeetingType = MeetingType.other
    attendees: list[str]
    preferred_windows: list[TimeWindow] = Field(default_factory=list)
    constraints: list[str]
    missing_fields: list[str]
    sensitivity: RiskLevel = RiskLevel.low
    async_candidate: bool = False
    escalation_required: bool = False


class MeetingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1)
    intent: MeetingIntent


class ParseRequestInput(BaseModel):
    raw_text: str = Field(min_length=1)


class WorkingHours(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str


class ProtectedBlock(TimeWindow):
    label: str


class ExecutiveRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_name: str
    timezone: str
    working_hours: WorkingHours
    protected_blocks: list[ProtectedBlock]
    preferences: list[str]


class RecommendationRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: RiskLevel
    message: str


class ProposedSlot(TimeWindow):
    reason: str


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Decision
    confidence: float = Field(ge=0, le=1)
    rationale: list[str] = Field(min_length=1)
    risks: list[RecommendationRisk]
    risk_level: RiskLevel = RiskLevel.low
    safe_action: str = "human_review_before_external_action"
    proposed_slots: list[ProposedSlot]
    model_status: ModelStatus


class RecommendationInput(BaseModel):
    meeting_request: MeetingRequest
    rules: ExecutiveRules


class DraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str
    tone: Tone
    draft_type: DraftType = DraftType.clarify
    model_status: ModelStatus


class DraftResponseInput(BaseModel):
    meeting_request: MeetingRequest
    recommendation: Recommendation


class DecisionLogInput(BaseModel):
    meeting_request: MeetingRequest
    recommendation: Recommendation
    final_decision: str
    notes: str = ""


class DecisionLogEntry(DecisionLogInput):
    id: int
    created_at: datetime


class HealthResponse(BaseModel):
    status: str


class MockCalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    start: datetime
    end: datetime


JsonDict = dict[str, Any]
