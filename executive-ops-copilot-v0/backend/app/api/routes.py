from fastapi import APIRouter

from app.api import audit, calendar, drafts, evals, feedback, recommendations, requests, rules


router = APIRouter()
router.include_router(requests.router)
router.include_router(recommendations.router)
router.include_router(drafts.router)
router.include_router(rules.router)
router.include_router(calendar.router)
router.include_router(feedback.router)
router.include_router(evals.router)
router.include_router(audit.router)
