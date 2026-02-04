# Testing Strategy

## Test layers

- Unit tests: ranker, schemas, utilities.
- Integration tests: API endpoints with test DB.
- Contract tests: tool schemas and orchestrator I/O.
- E2E tests: chat flow in frontend (smoke).

## Recommender tests

- Determinism tests with fixed inputs.
- Feature validation tests for each signal.
- Coverage tests for minimum candidate counts.

## Orchestrator tests

- Tool selection logic under different intents.
- Validation failures and retries.
- Session state updates.

## Fixtures

- Use deterministic catalog fixtures with known scores.
- Store in `tests/fixtures/`.

## CI gating

- Unit + integration tests required for merge.
- E2E tests required for release.

