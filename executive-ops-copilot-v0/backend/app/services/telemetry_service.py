from app.db.audit import AuditRepository
from app.telemetry.ai_quality import build_ai_quality_dashboard
from app.telemetry.prometheus import build_prometheus_metrics


class TelemetryService:
    def __init__(self, audit_repository: AuditRepository) -> None:
        self.audit_repository = audit_repository

    def ai_dashboard(self, limit: int = 250) -> dict:
        return build_ai_quality_dashboard(self.audit_repository.list_ai_event_summaries(limit))

    def prometheus_metrics(self, health: dict, limit: int = 250) -> str:
        try:
            ai_dashboard = self.ai_dashboard(limit)
            scrape_error = None
        except Exception as exc:
            ai_dashboard = None
            scrape_error = type(exc).__name__
        return build_prometheus_metrics(health=health, ai_dashboard=ai_dashboard, scrape_error=scrape_error)
