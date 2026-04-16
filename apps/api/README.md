# API App

Purpose: FastAPI service for TravelTom APIs, orchestration, local auth, and backend persistence.
Ownership: Backend.

## What Lives Here

- `app/`: internal API package with routers, services, schemas, repositories, and DB wiring.
- `migrations/`: Alembic migration history.
- `Dockerfile`: production API container build.
- `alembic.ini`: Alembic configuration for repo-root migration commands.

## Runtime Responsibilities

- Serve versioned HTTP endpoints under `/api/v1`.
- Persist chat, recommendation, and auth session state.
- Run the TravelTom chat agent and orchestration logic.
- Execute deterministic recommendation queries backed by the recommender v3 pipeline.
- Expose health and auth endpoints used by local and deployed environments.

## Important Entrypoints

- `app/main.py`: FastAPI app construction and startup preload.
- `app/api/v1/chat.py`: planner chat endpoint.
- `app/api/v1/recommendations.py`: direct recommendation query endpoint.
- `app/api/v1/auth.py`: local auth lifecycle.
- `app/services/travel_tom_agent.py`: shared route-facing agent integration.

## Runtime Notes

- `/api/v1/chat` and `/api/v1/recommendations/query` both use the same deterministic recommendation path in `traveltom/recommendor/recommendor_v3.py`.
- `traveltom/recommendor/recommendor_v1.py` and `traveltom/recommendor/recommendor_v2.py` are historical references, not the active runtime path.
- Shared request and response contracts live under `app/schemas/`.
- Local auth is the currently implemented end-to-end auth/session path.
- Chat rate limiting distinguishes TravelTom-owned throttling from upstream provider rate limits.
- Local environments keep chat rate limiting off by default unless `CHAT_RATE_LIMIT_ENABLED=true`.

## Common Tasks

Install backend dependencies from the repo root:

```bash
pip install -e .[dev]
```

Run migrations from the repo root:

```bash
alembic -c apps/api/alembic.ini upgrade head
```

Start the API locally:

```bash
uvicorn app.main:app --reload --app-dir apps/api
```

Run backend-oriented tests:

```bash
python -m pytest tests/api tests/orchestrator tests/test_health.py -q
```

## Runtime Notes

- `/api/v1/chat` and `/api/v1/recommendations/query` both use the shared
  recommendation runtime in `apps/api/app/services/recommendation_runtime.py`.
- The active recommendation runtime reads PostgreSQL `catalog_items` and adapts
  that runtime catalog into the `recommendor_v3` retrieval/ranking shape.
- `traveltom/recommendor/recommendor_v1.py`,
  `traveltom/recommendor/recommendor_v2.py`, and
  `traveltom/recommendor/recommendor_v3.py` are available in repo, with
  `recommendor_v3.py` now serving as the active runtime recommendation path.
- The health endpoint is intentionally split by responsibility:
  - API router in `apps/api/app/api/v1/health.py`
  - Response schema in `apps/api/app/schemas/api/health.py`
  - Health payload helper in `apps/api/app/services/health_status.py`
- The chat endpoint is intentionally split by responsibility:
  - API router and orchestration wiring in `apps/api/app/api/v1/chat.py`
  - Request/response schemas in `apps/api/app/schemas/api/chat.py`
  - Transaction boundary in `apps/api/app/services/chat_uow.py`
  - Session/message/recommendation persistence in `apps/api/app/repositories/chat.py`
  - Session identity/state helpers in `apps/api/app/services/chat_persistence.py`
- Local auth is currently the implemented end-to-end auth/session lifecycle:
  - Auth routes live in `apps/api/app/api/v1/auth.py`
  - Local token signing and verification live in `apps/api/app/core/local_auth.py`
  - Persisted auth-session lifecycle helpers live in
    `apps/api/app/repositories/auth_sessions.py`
  - `POST /api/v1/auth/logout` revokes the current local bearer token
- Chat 429 classification distinguishes:
  - TravelTom-owned throttling (`error.code=rate_limit_exceeded`)
  - Upstream provider quota/rate-limit failures (`error.code=provider_rate_limited`)
- TravelTom-owned chat 429s include `details.retry_after_seconds`,
  `details.source=traveltom`, and a `Retry-After` response header.
- Local environments default chat rate limiting off unless
  `CHAT_RATE_LIMIT_ENABLED=true` is set explicitly.
- The recommendations endpoint is intentionally split by responsibility:
  - API router and HTTP mapping in `apps/api/app/api/v1/recommendations.py`
  - API request/response schemas in `apps/api/app/schemas/api/recommendations.py`
  - Tool execution + response validation in `apps/api/app/services/recommendation_query.py`
- The orchestrator deterministically extracts constraints from user messages and
  persists them in session state before invoking the recommender.
- When planner support is enabled, structured planner state patches are merged
  on top of deterministic extraction instead of replacing it.
- The orchestrator extracts request-level `filters.item_type` from user text
  (for example hotel, restaurant, activity) for recommendation queries.
- Chat orchestration requests top 5 recommendations per message by default.
- Local/dev chat responses expose diagnostics headers for planner/composer usage:
  - `X-TravelTom-Planner-Status`
  - `X-TravelTom-Planner-Used`
  - `X-TravelTom-Composer-Status`
  - `X-TravelTom-Composer-Used`
  - `X-TravelTom-Orchestration-Degraded`
  - `X-TravelTom-Fallback-Reason`
- Ollama structured orchestration now prefers the native `/api/chat` JSON-schema
  route before the OpenAI-compatible endpoint because it is more reliable for
  the current planner/composer schemas.
- Local Ollama planner/composer stages use higher effective timeout floors than
  the generic structured timeout budget so realistic prompts complete in local dev.

## Troubleshooting

- If Alembic says `Path doesn't exist: migrations`, run it from the repo root with `-c apps/api/alembic.ini`.
- If chat returns zero recommendations:
  1. Confirm data exists in PostgreSQL `catalog_items`
  2. Confirm `/api/v1/chat` response includes populated `state.constraints` for
     messages that include destination/dates/budget
  3. Restart the API process because catalog data is cached per process
  4. Verify `/api/v1/recommendations/query` returns non-empty results before
     debugging frontend rendering
- If provider-assisted chat feels too fast, too deterministic, or too robotic:
  1. Inspect `X-TravelTom-*` response headers in local/dev
  2. Look for `provider_stage_failed`, `provider_stage_skipped`,
     `provider_stage_degraded`, `planner_execution_failed`, and
     `orchestrator_turn_completed` in backend logs
  3. Confirm the active provider and stage timeouts are appropriate for the
     configured model
- If chat returns `429`:
  1. Inspect `error.code` in the response body
  2. If `rate_limit_exceeded`, use `Retry-After`, `details.retry_after_seconds`,
     and `X-Trace-ID` to diagnose TravelTom-owned throttling
  3. If `provider_rate_limited`, inspect provider quota/status and the same
     trace ID rather than changing TravelTom rate-limit policy

## Related Docs

- `app/README.md`
- `../../instructions/02-backend/`
- `../../instructions/04-llm-orchestrator/`
