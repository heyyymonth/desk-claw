from fastapi import APIRouter, Depends, Query

from app.api.deps import get_audit_service
from app.services.audit_service import AuditService


router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/ai")
def list_ai_audit_events(
    limit: int = Query(default=50, ge=1, le=250),
    service: AuditService = Depends(get_audit_service),
):
    return {"events": service.list_ai_events(limit), "limit": limit}


@router.get("/ai/metrics")
def ai_audit_metrics(
    limit: int = Query(default=250, ge=1, le=1000),
    service: AuditService = Depends(get_audit_service),
):
    return service.ai_metrics(limit)
