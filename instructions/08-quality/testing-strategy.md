# Testing Strategy

## Test layers

- Unit tests: ranker, schemas, utilities.
- Integration tests: API endpoints with test DB.
- Contract tests: tool schemas and orchestrator I/O.
- Backend smoke tests: live API checks for `/health`, `/chat`, and `/recommendations/query`.
- E2E tests: mocked planner chat flow in frontend plus live-backend planner
  release verification.
- Frontend static quality checks: TypeScript type-check and production build.

## Recommender tests

- Determinism tests with fixed inputs.
- Feature validation tests for each signal.
- Coverage tests for minimum candidate counts.

## Orchestrator tests

- Deterministic slot gating under different intents.
- Provider planner/composer degradation behavior.
- Planner-success flows that must preserve deterministic extraction results.
- Result-composer grounding checks, including rejection of skipped surfaced
  items and unsupported ranking/scoring claims.
- Session state updates and carry-forward query shaping.
- Generic trip setup that must ask for recommendation type once destination and
  dates are known.
- Unsupported request flows that must refuse the request without mutating trip
  state.
- Repair turns, meta turns, and empty-result flows.
- Curated deterministic copy variation should be tested by semantic assertions
  or allowed-variant membership, not brittle single-string snapshots.

## Fixtures

- Use deterministic catalog fixtures with known scores.
- Store in `tests/fixtures/`.

## CI gating

- Unit + integration tests required for merge.
- Backend smoke tooling must stay runnable:
  - `pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000`
  - `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled`
  - `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email smoke@example.com`
  - Smoke coverage must include greeting, hotel slot gating, complete hotel
    search, same-session refinement continuity, empty-results follow-up
    recovery, generic search-type clarification, preference carry-forward,
    repair-turn handling, unsupported-flight refusal, and direct deterministic
    recommendations.
- Frontend static quality checks (`npm run typecheck`, `npm run build`) required for merge when frontend code changes.
- E2E tests required for release.
  - Mocked planner E2E must cover one happy path and one recovery/continuity
    path.
  - Live-backend planner verification must run before release against seeded
    `catalog_items` with provider mode `disabled`. Provider-assisted `ollama`
    is an optional release gate when local model infrastructure is available.
  - Use explicit readiness checks instead of UI-only waiting: `/api/v1/health`
    must return `ok`, and `/api/v1/recommendations/query` must return at least
    one hotel result for a supported seeded destination before the browser flow
    starts.

## Backend commands

- `venv\Scripts\python.exe -m pytest tests -q`
- `venv\Scripts\python.exe -m pytest tests\orchestrator tests\api\test_chat.py -q`

## Frontend commands

- `cd apps/web && npm test`: Vitest unit + DOM/component suite
- `cd apps/web && npm run test:e2e`: Playwright planner smoke flow with mocked API responses
- `cd apps/web && npm run test:ci`: combined frontend automated test run
- `cd apps/web && npm run build`: required static verification for frontend changes
- `pwsh ./scripts/smoke-planner-live.ps1 -ApiBaseUrl http://localhost:8000 -Provider disabled`: live seeded backend planner UI verification. The script signs up through the UI when `-AuthMode enabled` is used; pass `-AuthMode disabled` only when the backend is intentionally running with auth disabled.
- `pwsh ./scripts/smoke-planner-live.ps1 -ApiBaseUrl http://localhost:8000 -Provider ollama`: optional provider-assisted release gate.

Run mocked E2E for fast frontend regression feedback and CI. Run the live
planner smoke only when a real API, migrated database, and seeded catalog are
available.
