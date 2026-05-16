import time
from typing import Any

from providers.base import ModelProvider, ProviderError
from schemas import ChatRequest, ChatResponse, Usage


class OpenAIProvider(ModelProvider):
    name = "openai"

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def health_url(self) -> str:
        return f"{self.config.base_url}/models"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        model = request.model or self.config.default_model
        payload: dict[str, Any] = {
            "model": model,
            "input": [message.model_dump() for message in request.messages],
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
            "store": False,
        }
        body, headers = await self._post_json(f"{self.config.base_url}/responses", payload, self._headers())
        return self._response(
            model=body.get("model", model),
            content=_response_text(body),
            usage=_usage(body.get("usage", {})),
            finish_reason=_finish_reason(body),
            provider_request_id=headers.get("x-request-id") or headers.get("request-id"),
            started=started,
        )


def _response_text(body: dict[str, Any]) -> str:
    if isinstance(body.get("output_text"), str):
        return body["output_text"]
    chunks: list[str] = []
    for item in body.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if chunks:
        return "".join(chunks)
    raise ProviderError("openai", "Response did not include text output.")


def _usage(usage: dict[str, Any]) -> Usage:
    return Usage(
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


def _finish_reason(body: dict[str, Any]) -> str | None:
    for item in body.get("output", []):
        if isinstance(item, dict) and isinstance(item.get("finish_reason"), str):
            return item["finish_reason"]
    return body.get("status")
