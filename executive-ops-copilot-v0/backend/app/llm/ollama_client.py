import json
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel

from app.core.errors import ServiceError


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": schema.model_json_schema(),
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ServiceError("ollama_unavailable", "Ollama is unavailable. Use LLM_MODE=mock for tests.") from exc

        raw_response = body.get("response")
        if not isinstance(raw_response, str):
            raise ServiceError("ollama_invalid_response", "Ollama returned an invalid response envelope.")
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ServiceError("ollama_invalid_json", "Ollama returned non-JSON model output.") from exc
