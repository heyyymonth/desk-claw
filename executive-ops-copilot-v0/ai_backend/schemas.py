from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["system", "developer", "user", "assistant"]
ProviderName = Literal["ollama", "openai", "anthropic", "gemini"]


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    provider: ProviderName | None = None
    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = 0.2
    max_tokens: int | None = 1000
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    id: str
    provider: str
    model: str
    content: str
    usage: Usage = Field(default_factory=Usage)
    latency_ms: int
    finish_reason: str | None = None
    provider_request_id: str | None = None
    fallback_used: bool = False
    primary_provider_error: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ProviderHealth(BaseModel):
    configured: bool
    reachable: bool
    auth: str
    base_url: str
    default_model: str
    status_code: int | None = None
    message: str | None = None


class TestChatPayload(BaseModel):
    message: str = Field(min_length=1)
