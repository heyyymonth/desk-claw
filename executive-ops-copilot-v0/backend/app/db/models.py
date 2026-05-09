from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DecisionRecord:
    id: str
    action: str
    recommendation_id: str | None
    notes: str | None
    created_at: datetime
