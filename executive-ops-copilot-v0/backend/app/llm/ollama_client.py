import json
import urllib.error
import urllib.request


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def has_model(self) -> bool:
        request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=min(self.timeout_seconds, 2.0)) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return False

        models = body.get("models")
        if not isinstance(models, list):
            return False
        return any(model.get("name") == self.model or model.get("model") == self.model for model in models if isinstance(model, dict))
