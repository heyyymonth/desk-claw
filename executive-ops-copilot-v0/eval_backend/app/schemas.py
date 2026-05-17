from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "normal", "high", "urgent"]
RiskLevel = Literal["low", "medium", "high"]
MeetingType = Literal[
    "intro",
    "internal",
    "customer",
    "investor",
    "candidate",
    "vendor",
    "partner",
    "board",
    "legal_hr",
    "personal",
    "other",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeWindow(StrictModel):
    start: str
    end: str


class ExpectedIntent(StrictModel):
    title: str = ""
    requester: str
    duration_minutes: int = Field(ge=15, le=240)
    priority: Priority
    meeting_type: MeetingType = "other"
    attendees: list[str]
    preferred_windows: list[TimeWindow] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    sensitivity: RiskLevel = "low"
    async_candidate: bool = False
    escalation_required: bool = False


class EvalCaseBase(StrictModel):
    name: str = Field(min_length=1)
    description: str = ""
    prompt: str = Field(min_length=1)
    expected: ExpectedIntent
    active: bool = True


class EvalCaseCreate(EvalCaseBase):
    pass


class EvalCaseUpdate(EvalCaseBase):
    pass


class EvalCase(EvalCaseBase):
    id: str
    created_at: datetime
    updated_at: datetime


class FieldDiff(StrictModel):
    field: str
    expected: Any
    actual: Any
    passed: bool
    message: str = ""


class EvalCaseResult(StrictModel):
    id: str
    run_id: str
    case_id: str
    case_name: str
    status: Literal["passed", "failed", "invalid_output", "provider_error"]
    passed: bool
    score: float
    latency_ms: int | None = None
    provider: str | None = None
    model: str | None = None
    raw_output: str = ""
    normalized_output: dict[str, Any] | None = None
    expected: ExpectedIntent
    diffs: list[FieldDiff]
    error: str | None = None
    created_at: datetime


class EvalRunSummary(StrictModel):
    id: str
    created_at: datetime
    total_cases: int
    passed_cases: int
    pass_rate: float
    avg_latency_ms: float | None = None


class EvalRunDetail(EvalRunSummary):
    results: list[EvalCaseResult]


class HealthResponse(StrictModel):
    status: str
    service: str
    ai_backend_url: str
