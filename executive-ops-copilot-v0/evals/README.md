# Evals

Fixed cases for messy meeting request parsing and recommendation quality checks.

- `cases/v0_scheduling_cases.yaml` defines V0 scheduling scenarios.
- `expected/v0_expected_outputs.yaml` defines schema, safety, parse, recommendation, and draft expectations.
- The V0 runner should use backend APIs and validate outputs against `/contracts/schemas` before applying qualitative assertions.
