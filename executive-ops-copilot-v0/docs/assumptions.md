# Assumptions

## Product

- V0 runs as a local web app with one frontend process and one backend process.
- V0 supports one executive profile only.
- V0 supports one active local user; `actor_id` is optional and reserved for future auth.
- Dates and times are represented as ISO 8601 strings with timezone offsets.
- If the pasted request omits duration, the backend assumes 30 minutes and records `duration_minutes` as inferred.
- If the pasted request omits timezone, the backend uses the executive profile timezone.
- Calendar data is local mock context in V0, not a real calendar integration.
- Calendar blocks represent busy, tentative, hold, travel, or focus time.
- Proposed slots must not overlap hard busy blocks unless the recommendation explicitly reports a high risk.
- Ollama is expected at `http://localhost:11434` unless configured otherwise.
- The default V0 model is local Ollama `gemma4:latest`, routed through ADK as `ollama_chat/gemma4:latest`.
- ADK model routing is configurable through `ADK_MODEL`; request parsing, recommendation reasoning, and draft generation use Google ADK agent runners when enabled, with deterministic fallback behavior when the configured model is unavailable.
- Decision logs are local development data and are not encrypted in V0.
- Draft responses are editable by the user and are not sent automatically.
- `GET /api/decisions` returns newest entries first unless query parameters specify otherwise.
- `POST /api/evals/run` is a local development endpoint and does not run external network calls.

## Enterprise Boundaries

- AI is never the source of truth for calendar math. Backend calendar services and deterministic fixtures own availability, overlap, timezone, and slot calculations.
- AI output is validated into typed backend models before any recommendation or draft is shown as usable output.
- V0 has no calendar write-back, invite creation, email send, or message send behavior.
- V0 has no hidden data ingestion. Inputs are explicit pasted requests, local rules, local mock calendar blocks, and local development fixtures.
- V0 must not request broad OAuth scopes. Any future OAuth connector must request the narrowest documented scopes needed for that connector.
- No secrets, tokens, API keys, private calendar payloads, or real customer data may be committed.
- The frontend must not call Ollama directly. All model access is routed through the backend.
- Local-only does not mean fully offline once real connectors are added. Future connector behavior may require network access and must document that explicitly.
- All future connector assumptions must be documented before implementation, including data source, scopes, retention, sync/write behavior, failure handling, and audit requirements.

## Eval Assumptions

- V0 scheduling evals use a deterministic fixture week starting `2026-05-11` in `America/Los_Angeles` unless a case overrides calendar context.
- The eval endpoint includes Google ADK trajectory evaluation for scheduling tool calls and does not require an external hosted model.
- Eval expectations rely on first-class response fields for meeting type, draft type, sensitivity, async candidacy, escalation requirement, aggregate risk level, and safe action.
- Missing-context detection should prefer clarification or blocking behavior over speculative scheduling when requester identity, purpose, duration, authorization, attendee list, or sensitivity context is unclear.
- Sensitive legal, HR, board, disclosure, and press-related requests require human review before any outward-facing reply is treated as final.
- Recommendations may draft language for review, but they must not imply an invite was sent, a calendar was modified, or an external action was completed.
