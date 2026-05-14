from datetime import datetime, time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

Priority = Literal["low", "normal", "high", "urgent"]
Decision = Literal["schedule", "decline", "clarify", "defer"]
RiskLevel = Literal["low", "medium", "high"]
ModelStatus = Literal["used", "unavailable", "invalid_output", "not_configured"]
FeedbackAction = Literal["accept", "edit", "reject", "mark_wrong"]
MeetingType = Literal["intro", "internal", "customer", "investor", "candidate", "vendor", "partner", "board", "legal_hr", "personal", "other"]
DraftType = Literal["accept", "decline", "clarify", "defer"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeWindow(StrictModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def end_must_follow_start(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class MeetingIntent(StrictModel):
    title: str = Field(min_length=1)
    requester: str = Field(min_length=1)
    duration_minutes: int = Field(ge=15, le=240)
    priority: Priority
    meeting_type: MeetingType = "other"
    attendees: list[str]
    preferred_windows: list[TimeWindow] = Field(default_factory=list)
    constraints: list[str]
    missing_fields: list[str]
    sensitivity: RiskLevel = "low"
    async_candidate: bool = False
    escalation_required: bool = False


class ParsedMeetingRequest(StrictModel):
    raw_text: str = Field(min_length=1)
    intent: MeetingIntent


class WorkingHours(StrictModel):
    start: time
    end: time

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_hhmm(cls, value):
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            return time.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def end_must_follow_start(self):
        if self.end <= self.start:
            raise ValueError("working_hours.end must be after start")
        return self

    @field_serializer("start", "end")
    def serialize_hhmm(self, value: time) -> str:
        return value.strftime("%H:%M")


class ProtectedBlock(TimeWindow):
    label: str = Field(min_length=1)


class ExecutiveRules(StrictModel):
    executive_name: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    working_hours: WorkingHours
    protected_blocks: list[ProtectedBlock]
    preferences: list[str]


class Risk(StrictModel):
    level: RiskLevel
    message: str = Field(min_length=1)


class ProposedSlot(TimeWindow):
    reason: str = Field(min_length=1)


class Recommendation(StrictModel):
    decision: Decision
    confidence: float = Field(ge=0, le=1)
    rationale: list[str] = Field(min_length=1)
    risks: list[Risk]
    risk_level: RiskLevel = "low"
    safe_action: str = Field(default="human_review_before_external_action", min_length=1)
    proposed_slots: list[ProposedSlot]
    model_status: ModelStatus


class DraftResponse(StrictModel):
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    tone: Literal["concise", "warm", "firm"]
    draft_type: DraftType = "clarify"
    model_status: ModelStatus


class CalendarBlock(TimeWindow):
    title: str = Field(min_length=1)
    busy: bool = True


class CalendarAnalysis(StrictModel):
    conflicts: list[CalendarBlock]
    open_slots: list[ProposedSlot]


class RuleViolation(StrictModel):
    code: str
    message: str


class DecisionFeedback(StrictModel):
    action: FeedbackAction
    recommendation_id: str | None = None
    notes: str | None = None


class DecisionLogEntry(DecisionFeedback):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ParseRequestPayload(StrictModel):
    raw_text: str = Field(min_length=1)


class RecommendationPayload(StrictModel):
    parsed_request: ParsedMeetingRequest
    rules: ExecutiveRules
    calendar_blocks: list[CalendarBlock] = Field(default_factory=list)


class DraftPayload(StrictModel):
    recommendation: Recommendation


class DecisionsResponse(StrictModel):
    decisions: list[DecisionLogEntry]


class CalendarResponse(StrictModel):
    blocks: list[CalendarBlock]
