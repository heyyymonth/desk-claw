# ADR 0002: AI Boundaries and Enterprise Safety in V0

## Status

Accepted

## Context

V0 uses local model assistance to parse messy scheduling requests and help draft responses. Enterprise use requires clear product boundaries before real calendar, inbox, identity, or CRM connectors are introduced. The system must support human review, contract validation, and predictable fallback behavior without implying that local model output is authoritative.

## Decision

V0 treats AI as an assistant for structured extraction and draft text only. The backend remains the authority for validation, policy orchestration, calendar math, recommendation decisions, and persistence.

V0 will enforce these boundaries:

- AI output is validated against typed backend models before use.
- Calendar availability, overlaps, timezones, and proposed slots come from backend calendar logic and fixtures, not model reasoning.
- The frontend calls backend APIs only and never calls Ollama directly.
- The product does not write back to calendars, create invites, send email, or send messages in V0.
- Draft responses are editable human-review artifacts, not autonomous communications.
- No hidden data ingestion is allowed; all inputs must be explicit and visible to the workflow.
- No broad OAuth scopes are allowed in V0.
- Secrets and real private data must not be committed to code, fixtures, evals, logs, or docs.
- Any future connector must document data source, scopes, retention, read/write behavior, failure modes, audit needs, and offline/network assumptions before implementation.

## Consequences

- V0 can be evaluated safely with mock calendar context and deterministic backend fixtures.
- Missing or sensitive context should produce clarification, deferral, escalation, or blocking recommendations rather than speculative scheduling.
- Product-quality labels used in evals, such as meeting type, draft type, sensitivity, async candidacy, escalation requirement, aggregate risk level, and safe action, are authoritative V0 API fields because they are included in typed models and JSON Schema contracts.
- Adding real connectors will require new assumptions, contract updates, tests, and security review.
