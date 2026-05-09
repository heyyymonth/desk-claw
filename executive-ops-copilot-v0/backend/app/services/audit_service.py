from app.db.audit import AuditEvent, AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def log_ai_event(self, event: AuditEvent) -> str:
        return self.repository.add_ai_event(event)

    def list_ai_events(self, limit: int = 50) -> list[dict]:
        return self.repository.list_ai_events(limit)
