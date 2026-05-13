import json
import time
import urllib.error
import urllib.request

from app.core.settings import Settings


class ModelWarmupError(RuntimeError):
    pass


def warm_ollama_model(settings: Settings) -> dict:
    if settings.llm_mode != "ollama" or not settings.warm_ollama_on_startup:
        return {"status": "skipped", "reason": "warmup_disabled"}

    started = time.perf_counter()
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": "Reply ok only."}],
        "stream": False,
        "keep_alive": "30m",
    }
    request = urllib.request.Request(
        f"{settings.ollama_base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.ollama_warmup_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ModelWarmupError(f"Ollama warmup failed for {settings.ollama_model}: {exc}") from exc

    return {
        "status": "ready",
        "model": body.get("model", settings.ollama_model),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "ollama_total_seconds": round((body.get("total_duration") or 0) / 1_000_000_000, 3),
        "ollama_load_seconds": round((body.get("load_duration") or 0) / 1_000_000_000, 3),
    }
