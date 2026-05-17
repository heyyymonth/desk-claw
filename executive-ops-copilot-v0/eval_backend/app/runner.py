import time
import uuid
from datetime import UTC, datetime

import httpx

from app.schemas import EvalCase, EvalCaseResult, FieldDiff
from app.scoring import parse_model_content, safe_validation_error, score_output, validate_expected_shape

EVAL_SYSTEM_PROMPT = (
    "You are an eval parser for executive scheduling requests. Return only one minified JSON object matching the "
    "meeting intent schema with fields: title, requester, duration_minutes, priority, meeting_type, attendees, "
    "preferred_windows, constraints, missing_fields, sensitivity, async_candidate, escalation_required. "
    "Do not include markdown or prose. Use priority low, normal, high, or urgent. Use meeting_type intro, internal, "
    "customer, investor, candidate, vendor, partner, board, legal_hr, personal, or other. Use sensitivity low, "
    "medium, or high."
)


class EvalRunner:
    def __init__(self, ai_backend_url: str, timeout_seconds: float) -> None:
        self.ai_backend_url = ai_backend_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def run_case(self, run_id: str, case: EvalCase) -> EvalCaseResult:
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self.ai_backend_url}/v1/chat",
                json={
                    "messages": [
                        {"role": "system", "content": EVAL_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                "Parse this scheduling request into the schema. "
                                f"Request: {case.prompt}"
                            ),
                        },
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1200,
                    "stream": False,
                    "metadata": {"source": "eval-backend", "case_id": case.id, "run_id": run_id},
                },
                timeout=self.timeout_seconds,
            )
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"AI Backend returned HTTP {response.status_code}",
                    request=httpx.Request("POST", f"{self.ai_backend_url}/v1/chat"),
                    response=response,
                )
            body = response.json()
            raw_output = body.get("content") if isinstance(body.get("content"), str) else ""
            latency_ms = body.get("latency_ms") if isinstance(body.get("latency_ms"), int) else int((time.perf_counter() - started) * 1000)
            actual = parse_model_content(raw_output)
            validate_expected_shape(actual)
            passed, score, diffs = score_output(actual, case.expected)
            return EvalCaseResult(
                id=str(uuid.uuid4()),
                run_id=run_id,
                case_id=case.id,
                case_name=case.name,
                status="passed" if passed else "failed",
                passed=passed,
                score=score,
                latency_ms=latency_ms,
                provider=body.get("provider") if isinstance(body.get("provider"), str) else None,
                model=body.get("model") if isinstance(body.get("model"), str) else None,
                raw_output=raw_output,
                normalized_output=actual,
                expected=case.expected,
                diffs=diffs,
                error=None,
                created_at=datetime.now(UTC),
            )
        except (ValueError, TypeError) as exc:
            return self._failure(run_id, case, "invalid_output", str(exc), int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            return self._failure(run_id, case, "provider_error", safe_validation_error(exc), int((time.perf_counter() - started) * 1000))

    def _failure(self, run_id: str, case: EvalCase, status: str, error: str, latency_ms: int) -> EvalCaseResult:
        return EvalCaseResult(
            id=str(uuid.uuid4()),
            run_id=run_id,
            case_id=case.id,
            case_name=case.name,
            status=status,  # type: ignore[arg-type]
            passed=False,
            score=0.0,
            latency_ms=latency_ms,
            provider=None,
            model=None,
            raw_output="",
            normalized_output=None,
            expected=case.expected,
            diffs=[
                FieldDiff(
                    field="output",
                    expected=case.expected.model_dump(mode="json"),
                    actual=None,
                    passed=False,
                    message=error,
                )
            ],
            error=error,
            created_at=datetime.now(UTC),
        )
