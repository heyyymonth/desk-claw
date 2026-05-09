# E2E

Playwright tests for the local scheduling workflow.

```bash
npm install
npm run test:e2e
```

From the repository root, the same suite can be run with:

```bash
./scripts/run-e2e.sh
```

The tests mock `/api/**` in the browser with seeded V0 data, so they do not require real calendar, email, Slack, Microsoft, Google, or Ollama integrations.
