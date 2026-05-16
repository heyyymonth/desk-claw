import time
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

import httpx

from config import ProviderConfig
from schemas import ChatRequest, ChatResponse, ProviderHealth, Usage


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, status_code: int | None = None) -> None:
        self.provider = provider
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def safe_detail(self) -> dict[str, Any]:
        return {"provider": self.provider, "status_code": self.status_code, "message": self.message}


class ModelProvider(ABC):
    name: str

    def __init__(self, config: ProviderConfig, timeout_seconds: float, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @property
    def default_model(self) -> str:
        return self.config.default_model

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport)

    async def health_check(self) -> ProviderHealth:
        if not self.config.configured:
            return self._health(False, False, "missing")
        try:
            async with self._client() as client:
                response = await client.get(self.health_url(), headers=self._headers())
            return self._health(True, response.status_code < 400, "valid" if response.status_code < 400 else "invalid", response.status_code)
        except httpx.TimeoutException:
            return self._health(True, False, "unknown", message="Timed out")
        except httpx.HTTPError as exc:
            return self._health(True, False, "unknown", message=str(exc))

    @abstractmethod
    def health_url(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    def _require_configured(self) -> None:
        if not self.config.configured:
            raise ProviderError(self.name, f"{self.name} provider is not configured.")

    def _health(
        self,
        configured: bool,
        reachable: bool,
        auth: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> ProviderHealth:
        return ProviderHealth(
            configured=configured,
            reachable=reachable,
            auth=auth,
            base_url=self.config.base_url,
            default_model=self.config.default_model,
            status_code=status_code,
            message=message,
        )

    async def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[dict[str, Any], httpx.Headers]:
        self._require_configured()
        try:
            async with self._client() as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                raise ProviderError(self.name, self._status_message(response.status_code), response.status_code)
            return response.json(), response.headers
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(self.name, "Provider request timed out.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(self.name, "Provider request failed.") from exc

    def _response(
        self,
        *,
        model: str,
        content: str,
        usage: Usage | None = None,
        finish_reason: str | None = None,
        provider_request_id: str | None = None,
        started: float,
        raw: dict[str, Any] | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            id=f"airesp_{uuid4().hex}",
            provider=self.name,
            model=model,
            content=content,
            usage=usage or Usage(),
            latency_ms=int((time.perf_counter() - started) * 1000),
            finish_reason=finish_reason,
            provider_request_id=provider_request_id,
            raw=raw or {},
        )

    def _status_message(self, status_code: int) -> str:
        if status_code in {401, 403}:
            return "Authentication failed"
        if status_code == 429:
            return "Rate limited"
        return f"Provider returned HTTP {status_code}"
