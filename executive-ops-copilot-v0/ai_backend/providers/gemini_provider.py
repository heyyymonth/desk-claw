import time

from providers.base import ModelProvider
from schemas import ChatRequest, ChatResponse, Usage


class GeminiProvider(ModelProvider):
    name = "gemini"

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.config.api_key:
            headers["x-goog-api-key"] = self.config.api_key
        return headers

    def health_url(self) -> str:
        return f"{self.config.base_url}/{self.config.extra['api_version']}/models"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        model = request.model or self.config.default_model
        system = "\n\n".join(message.content for message in request.messages if message.role in {"system", "developer"})
        contents = [
            {"role": "model" if message.role == "assistant" else "user", "parts": [{"text": message.content}]}
            for message in request.messages
            if message.role in {"user", "assistant"}
        ]
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{self.config.base_url}/{self.config.extra['api_version']}/models/{model}:generateContent"
        body, headers = await self._post_json(url, payload, self._headers())
        candidate = body.get("candidates", [{}])[0] if isinstance(body.get("candidates"), list) and body.get("candidates") else {}
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        return self._response(
            model=model,
            content="".join(part.get("text", "") for part in parts if isinstance(part, dict)),
            usage=_usage(body.get("usageMetadata", {})),
            finish_reason=candidate.get("finishReason") if isinstance(candidate, dict) else None,
            provider_request_id=headers.get("x-request-id"),
            started=started,
        )


def _usage(usage: dict) -> Usage:
    return Usage(
        input_tokens=usage.get("promptTokenCount"),
        output_tokens=usage.get("candidatesTokenCount"),
        total_tokens=usage.get("totalTokenCount"),
    )
