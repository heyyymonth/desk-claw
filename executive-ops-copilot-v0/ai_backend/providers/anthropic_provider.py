import time

from providers.base import ModelProvider
from schemas import ChatRequest, ChatResponse, Usage


class AnthropicProvider(ModelProvider):
    name = "anthropic"

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        headers["anthropic-version"] = self.config.extra["version"]
        return headers

    def health_url(self) -> str:
        return f"{self.config.base_url}/v1/models"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        model = request.model or self.config.default_model
        system = "\n\n".join(message.content for message in request.messages if message.role in {"system", "developer"})
        messages = [
            {"role": message.role, "content": message.content}
            for message in request.messages
            if message.role in {"user", "assistant"}
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or 1000,
        }
        if system:
            payload["system"] = system
        body, headers = await self._post_json(f"{self.config.base_url}/v1/messages", payload, self._headers())
        return self._response(
            model=body.get("model", model),
            content="".join(block.get("text", "") for block in body.get("content", []) if isinstance(block, dict)),
            usage=_usage(body.get("usage", {})),
            finish_reason=body.get("stop_reason"),
            provider_request_id=headers.get("request-id"),
            started=started,
        )


def _usage(usage: dict) -> Usage:
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total = input_tokens + output_tokens if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total)
