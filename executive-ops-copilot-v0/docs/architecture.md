# Architecture

The app now runs as three separate services:

```text
Frontend
  -> Web Backend
  -> AI Backend
  -> Provider Adapter
  -> Ollama/OpenAI/Anthropic/Gemini
```

## Responsibilities

| Service | Owns | Does not own |
| --- | --- | --- |
| Frontend | UI, browser interactions, calls to Web Backend | Model calls, provider keys, AI routing |
| Web Backend | Product APIs, scheduling workflow, validation, guardrails, response shaping | Provider SDKs, provider keys, provider base URLs |
| AI Backend | Model routing, provider adapters, provider health, retries/fallback, normalized AI responses | Product UI, product DB logic, scheduling business rules |

## Runtime Flow

```text
raw text
  -> POST /api/parse-request
  -> Web Backend validation and scheduling workflow
  -> AI Backend /v1/chat for model-backed JSON steps
  -> provider adapter
  -> normalized model response
  -> guarded Web Backend product response
```

The compatibility frontend route remains `POST /api/parse-request`. A simple model smoke route is also available at `POST /api/chat`.
