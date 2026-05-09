# ADR 0001: Local Web App With FastAPI-Owned Orchestration

## Status

Accepted

## Context

V0 needs to validate the scheduling workflow before calendar, inbox, or enterprise integrations are introduced. The assistant should remain local, contract-first, and testable.

## Decision

Use a local React + TypeScript + Vite frontend, a FastAPI backend, SQLite persistence, and Ollama for local Gemma model calls. The frontend only calls FastAPI. FastAPI owns validation, orchestration, business policy, recommendation generation, persistence, and model access.

## Consequences

- The backend can enforce schema validation around all AI outputs.
- The frontend remains a workflow UI rather than a model client.
- Calendar and inbox integrations can be added later without changing the user-facing workflow contract.
- Local setup requires Python, Node, and Ollama for full model-backed behavior.
