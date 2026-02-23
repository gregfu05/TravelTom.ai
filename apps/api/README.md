# API App

Purpose: FastAPI service for TravelTom APIs, orchestration, and backend services.
Ownership: Backend.

See `instructions/02-backend/` for design and API contracts.

## Runtime notes

- `/api/v1/chat` and `/api/v1/recommendations/query` both use the same deterministic
  recommender implementation in `traveltom/recommendor/recommendor_v1.py`.
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
