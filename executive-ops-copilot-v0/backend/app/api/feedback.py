from fastapi import APIRouter, Depends, status

from app.api.deps import get_decision_log_service, get_workflow_decision_log_service
from app.llm.schemas import DecisionFeedback, DecisionLogEntry
from app.models import DecisionLogEntry as WorkflowDecisionLogEntry
from app.models import DecisionLogInput
from app.services.decision_log import DecisionLogService
from app.services.workflow_decision_log import WorkflowDecisionLogService


router = APIRouter(tags=["feedback"])


@router.post("/api/feedback", response_model=DecisionLogEntry, status_code=status.HTTP_201_CREATED)
def log_feedback(
    payload: DecisionFeedback,
    service: DecisionLogService = Depends(get_decision_log_service),
):
    return service.log(payload)


@router.get("/api/decisions", response_model=list[WorkflowDecisionLogEntry])
def list_workflow_decisions(
    service: WorkflowDecisionLogService = Depends(get_workflow_decision_log_service),
):
    return service.list()


@router.post("/api/decisions", response_model=WorkflowDecisionLogEntry, status_code=status.HTTP_201_CREATED)
def log_workflow_decision(
    payload: DecisionLogInput,
    service: WorkflowDecisionLogService = Depends(get_workflow_decision_log_service),
):
    return service.log(payload)
