from fastapi import APIRouter

from app.api import audit, calendar, drafts, evals, feedback, metrics, recommendations, requests, rules, telemetry

router = APIRouter()
router.include_router(requests.router)
router.include_router(recommendations.router)
router.include_router(drafts.router)
router.include_router(rules.router)
router.include_router(calendar.router)
router.include_router(feedback.router)
router.include_router(evals.router)
router.include_router(audit.router)
router.include_router(telemetry.router)
router.include_router(metrics.router)
