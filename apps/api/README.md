# API App

Purpose: FastAPI service for TravelTom APIs, orchestration, and backend services.
Ownership: Backend.

See `instructions/02-backend/` for design and API contracts.

## Runtime notes

- `/api/v1/chat` and `/api/v1/recommendations/query` both use the same deterministic
  recommender implementation in `traveltom/recommendor/recommendor_v2.py` (Yelp
  parquet, in-process).
  recommender implementation in `traveltom/recommendor/recommendor_v1.py`.
- The health endpoint is intentionally split by responsibility:
  - API router in `apps/api/app/api/v1/health.py`.
  - Response schema in `apps/api/app/schemas/api/health.py`.
  - Health payload helper in `apps/api/app/services/health_status.py`.
- The chat endpoint is intentionally split by responsibility:
  - API router and orchestration wiring in `apps/api/app/api/v1/chat.py`.
  - Request/response schemas in `apps/api/app/schemas/api/chat.py`.
  - Transaction boundary in `apps/api/app/services/chat_uow.py`.
  - Session/message/recommendation persistence in `apps/api/app/repositories/chat.py`.
  - Session identity/state helpers in `apps/api/app/services/chat_persistence.py`.
- Local auth is currently the implemented end-to-end auth/session lifecycle:
  - Auth routes live in `apps/api/app/api/v1/auth.py`.
  - Local token signing and verification live in `apps/api/app/core/local_auth.py`.
  - Persisted auth-session lifecycle helpers live in
    `apps/api/app/repositories/auth_sessions.py`.
  - `POST /api/v1/auth/logout` revokes the current local bearer token.
- Chat 429 classification now distinguishes:
  - TravelTom-owned throttling (`error.code=rate_limit_exceeded`) from
    `enforce_chat_rate_limit`.
  - Upstream provider quota/rate-limit failures (`error.code=provider_rate_limited`).
- TravelTom-owned chat 429s include `details.retry_after_seconds`,
  `details.source=traveltom`, and a `Retry-After` response header.
- Local environments default chat rate limiting off unless
  `CHAT_RATE_LIMIT_ENABLED=true` is set explicitly.
- The recommendations endpoint is intentionally split by responsibility:
  - API router and HTTP mapping in `apps/api/app/api/v1/recommendations.py`.
  - API request/response schemas in `apps/api/app/schemas/api/recommendations.py`.
  - Tool execution + response validation in `apps/api/app/services/recommendation_query.py`.
- The v2 recommender reads candidates from `traveltom/datasets/cleaned_Yelp_DS.parquet`
  (no DB seeding required for local tests).
- The recommender reads candidates from PostgreSQL `catalog_items` (seed this
  table before testing chat recommendations).
- The orchestrator deterministically extracts constraints from user messages and
  persists them in session state before invoking the recommender.
- The orchestrator also extracts request-level `filters.item_type` from user
  text (for example hotel, flight, destination) for recommendation queries.
- The recommender applies a destination hard filter from
  `constraints.destination` against catalog city names.
- Chat orchestration requests top 5 recommendations per message by default
  (`max_recommendation_results` policy).
- Recommender DB reads use a dedicated DB connection path and do not reuse
  request-scoped async sessions.

## Troubleshooting

- If migrations fail with `Path doesn't exist: migrations`, run Alembic from repo root:
  `alembic -c apps/api/alembic.ini upgrade head`
- If chat returns zero recommendations:
  1. Seed data: `python scripts/seed_catalog.py --truncate`
  2. Confirm DB rows: `SELECT COUNT(*) FROM catalog_items;`
  3. Confirm `/api/v1/chat` response includes populated `state.constraints` for
     messages that include destination/dates/budget.
  4. Restart the API process (catalog snapshot is cached per process).
  5. Verify `/api/v1/recommendations/query` returns non-empty results before
     debugging frontend rendering.
- If chat returns `429`:
  1. Inspect `error.code` in the response body.
  2. If `rate_limit_exceeded`, use `Retry-After`, `details.retry_after_seconds`,
     and `X-Trace-ID` to diagnose TravelTom-owned throttling.
  3. If `provider_rate_limited`, inspect provider quota/status and the same
     trace ID rather than changing TravelTom rate-limit policy.
