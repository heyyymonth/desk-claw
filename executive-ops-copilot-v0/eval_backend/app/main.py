import json
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.runner import EvalRunner
from app.schemas import EvalCase, EvalCaseCreate, EvalRunDetail, EvalRunSummary, HealthResponse
from app.settings import get_settings
from app.store import EvalStore


def load_seed_cases() -> list[EvalCaseCreate]:
    seed_path = Path(__file__).with_name("seed_cases.json")
    return [EvalCaseCreate.model_validate(item) for item in json.loads(seed_path.read_text())]


@lru_cache
def get_store() -> EvalStore:
    settings = get_settings()
    store = EvalStore(settings.eval_db_path)
    store.seed_cases(load_seed_cases())
    return store


def create_app() -> FastAPI:
    app = FastAPI(title="Desk Claw Eval Backend", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    def health():
        settings = get_settings()
        return HealthResponse(status="ok", service="eval-backend", ai_backend_url=settings.ai_backend_url)

    @app.get("/api/eval-cases", response_model=list[EvalCase])
    def list_cases():
        return get_store().list_cases()

    @app.post("/api/eval-cases", response_model=EvalCase)
    def create_case(case: EvalCaseCreate):
        return get_store().create_case(case)

    @app.put("/api/eval-cases/{case_id}", response_model=EvalCase)
    def update_case(case_id: str, case: EvalCaseCreate):
        updated = get_store().update_case(case_id, case)
        if updated is None:
            raise HTTPException(status_code=404, detail="Eval case not found")
        return updated

    @app.delete("/api/eval-cases/{case_id}")
    def delete_case(case_id: str):
        if not get_store().delete_case(case_id):
            raise HTTPException(status_code=404, detail="Eval case not found")
        return {"status": "deleted"}

    @app.post("/api/eval-runs", response_model=EvalRunDetail)
    def create_run():
        settings = get_settings()
        runner = EvalRunner(settings.ai_backend_url, settings.request_timeout_seconds)
        run_id = str(uuid.uuid4())
        cases = [case for case in get_store().list_cases() if case.active]
        results = [runner.run_case(run_id, case) for case in cases]
        return get_store().create_run(results)

    @app.get("/api/eval-runs", response_model=list[EvalRunSummary])
    def list_runs():
        return get_store().list_runs()

    @app.get("/api/eval-runs/{run_id}", response_model=EvalRunDetail)
    def get_run(run_id: str):
        run = get_store().get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Eval run not found")
        return run

    @app.post("/api/eval-runs/{run_id}/cases/{case_id}/rerun", response_model=EvalRunDetail)
    def rerun_case(run_id: str, case_id: str):
        if get_store().get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Eval run not found")
        case = get_store().get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Eval case not found")
        settings = get_settings()
        runner = EvalRunner(settings.ai_backend_url, settings.request_timeout_seconds)
        return get_store().create_run([runner.run_case(str(uuid.uuid4()), case)])

    return app


app = create_app()
