from collections.abc import Mapping

from providers.base import ModelProvider, ProviderError
from schemas import ChatRequest, ChatResponse


class ModelRouter:
    def __init__(
        self,
        providers: Mapping[str, ModelProvider],
        default_provider: str,
        fallback_provider: str | None,
    ) -> None:
        self.providers = dict(providers)
        self.default_provider = default_provider
        self.fallback_provider = fallback_provider

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if request.stream:
            raise ProviderError("router", "Streaming is not supported by this AI Backend endpoint.", 400)

        primary_name = request.provider or self.default_provider
        primary = self.providers.get(primary_name)
        errors: list[ProviderError] = []
        if primary is None:
            errors.append(ProviderError(primary_name, f"Unsupported provider: {primary_name}", 400))
        else:
            try:
                return await primary.chat(request)
            except ProviderError as exc:
                errors.append(exc)

        fallback_name = self.fallback_provider
        if fallback_name and fallback_name != primary_name:
            fallback = self.providers.get(fallback_name)
            if fallback is not None:
                try:
                    fallback_request = request.model_copy(update={"provider": fallback_name, "model": None})
                    response = await fallback.chat(fallback_request)
                    response.fallback_used = True
                    response.primary_provider_error = errors[0].message if errors else None
                    return response
                except ProviderError as exc:
                    errors.append(exc)

        if len(errors) == 1:
            raise errors[0]
        message = "Primary and fallback providers failed"
        raise ProviderError("router", f"{message}: {_safe_details(errors)}", 503)


def _safe_details(errors: list[ProviderError]) -> str:
    return "; ".join(f"{error.provider}: {error.message}" for error in errors)
