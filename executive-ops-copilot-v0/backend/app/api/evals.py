from fastapi import APIRouter


from app.evals.runner import run


router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.post("/run")
def run_evals():
    return run()
