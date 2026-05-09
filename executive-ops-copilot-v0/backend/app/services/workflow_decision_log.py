from app.db.decision_log import DecisionLogRepository
from app.models import DecisionLogEntry, DecisionLogInput


class WorkflowDecisionLogService:
    def __init__(self, repository: DecisionLogRepository) -> None:
        self.repository = repository

    def log(self, payload: DecisionLogInput) -> DecisionLogEntry:
        return self.repository.add(payload)

    def list(self) -> list[DecisionLogEntry]:
        return self.repository.list()
