from app.db.audit import AuditRepository
from app.telemetry.ai_quality import build_ai_quality_dashboard


class TelemetryService:
    def __init__(self, audit_repository: AuditRepository) -> None:
        self.audit_repository = audit_repository

    def ai_dashboard(self, limit: int = 250) -> dict:
        return build_ai_quality_dashboard(self.audit_repository.list_ai_events(limit))
