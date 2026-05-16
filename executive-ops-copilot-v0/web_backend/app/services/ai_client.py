import time
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from app.core.errors import ServiceError


class ChatPayload(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    content: str
    provider: str
    model: str
    latency_ms: int


class AiBackendClient:
    def __init__(self, base_url: str, timeout_seconds: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def chat(self, message: str) -> ChatResponse:
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": message},
            ],
            "provider": None,
            "model": None,
            "temperature": 0.2,
            "max_tokens": 1000,
            "stream": False,
            "metadata": {"source": "web-backend", "request_id": str(uuid4())},
        }
        try:
            response = httpx.post(f"{self.base_url}/v1/chat", json=payload, timeout=self.timeout_seconds)
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "AI Backend request failed",
                    request=httpx.Request("POST", f"{self.base_url}/v1/chat"),
                    response=response,
                )
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError(
                "ai_backend_unavailable",
                "The AI Backend is unavailable. Check service health before retrying.",
                status_code=502,
            ) from exc

        content = body.get("content")
        provider = body.get("provider")
        model = body.get("model")
        if not isinstance(content, str) or not isinstance(provider, str) or not isinstance(model, str):
            raise ServiceError(
                "ai_backend_invalid_response",
                "The AI Backend returned an invalid response shape.",
                status_code=502,
            )

        return ChatResponse(
            content=content,
            provider=provider,
            model=model,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
