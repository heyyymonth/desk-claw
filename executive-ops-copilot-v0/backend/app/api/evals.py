from fastapi import APIRouter

router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.post("/run")
def run_evals():
    from app.evals.runner import run

    return run()
