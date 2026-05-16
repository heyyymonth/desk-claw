import time

from app.agents import build_model_client
from app.core.settings import Settings
from app.services.ai_config_service import current_model_client_kwargs


class ModelWarmupError(RuntimeError):
    pass


def warm_model(settings: Settings) -> dict:
    if not settings.warm_model_on_startup:
        return {"status": "skipped", "reason": "warmup_disabled"}

    started = time.perf_counter()
    model_config = current_model_client_kwargs(settings)
    try:
        response = build_model_client(**model_config).complete_json(
            system_prompt="Return only JSON.",
            payload={"task": "Reply with JSON.", "required_output": {"ok": True}},
            timeout_seconds=settings.model_warmup_timeout_seconds,
        )
    except Exception as exc:
        raise ModelWarmupError(f"Model warmup failed for {model_config['provider']}:{model_config['model']}: {exc}") from exc

    return {
        "status": "ready",
        "provider": response.provider,
        "model": response.model_name,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
