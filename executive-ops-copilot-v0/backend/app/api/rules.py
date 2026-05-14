from fastapi import APIRouter

from app.llm.schemas import ExecutiveRules
from app.services.rules_engine import RulesEngine

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=ExecutiveRules)
def get_rules():
    return RulesEngine().default_rules()


@router.put("", response_model=ExecutiveRules)
def update_rules(payload: ExecutiveRules):
    return payload


@router.get("/default", response_model=ExecutiveRules)
def default_rules():
    return RulesEngine().default_rules()
