import time

from providers.base import ModelProvider
from schemas import ChatRequest, ChatResponse, Usage


class OllamaProvider(ModelProvider):
    name = "ollama"

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def health_url(self) -> str:
        return f"{self.config.base_url}/tags"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        model = request.model or self.config.default_model
        payload = {
            "model": model,
            "messages": [message.model_dump() for message in request.messages],
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        body, headers = await self._post_json(f"{self.config.base_url}/chat", payload, self._headers())
        message = body.get("message") if isinstance(body.get("message"), dict) else {}
        content = message.get("content") if isinstance(message.get("content"), str) else body.get("response", "")
        usage = Usage(
            input_tokens=body.get("prompt_eval_count") if isinstance(body.get("prompt_eval_count"), int) else None,
            output_tokens=body.get("eval_count") if isinstance(body.get("eval_count"), int) else None,
        )
        if usage.input_tokens is not None or usage.output_tokens is not None:
            usage.total_tokens = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        return self._response(
            model=body.get("model", model),
            content=content,
            usage=usage,
            finish_reason=body.get("done_reason") or "stop",
            provider_request_id=headers.get("x-request-id"),
            started=started,
        )
