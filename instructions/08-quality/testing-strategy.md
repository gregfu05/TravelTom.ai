# Testing Strategy

## Test layers

- Unit tests: ranker, schemas, utilities.
- Integration tests: API endpoints with test DB.
- Contract tests: tool schemas and orchestrator I/O.
- E2E tests: chat flow in frontend (smoke).
- Frontend static quality checks: TypeScript type-check and production build.

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
- Frontend static quality checks (`npm run typecheck`, `npm run build`) required for merge when frontend code changes.
- E2E tests required for release.

## Frontend commands

- `cd apps/web && npm test`: Vitest unit + DOM/component suite
- `cd apps/web && npm run test:e2e`: Playwright planner smoke flow with mocked API responses
- `cd apps/web && npm run test:ci`: combined frontend automated test run
- `cd apps/web && npm run build`: required static verification for frontend changes
