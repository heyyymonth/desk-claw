# Architecture

The app is a two-service request parser:

- React frontend: collects raw request text and renders the structured response.
- FastAPI backend: validates input, runs agent orchestration, and returns parsed intent plus recommended next steps.

Runtime flow:

```text
raw text
  -> POST /api/parse-request
  -> ParseRequestPayload validation
  -> RequestParser
  -> native parser agent or deterministic fallback
  -> RecommendationService planner
  -> DraftService
  -> ParseRequestResponse JSON
```

The frontend never calls a model provider. Model configuration and API keys stay in the backend environment.
