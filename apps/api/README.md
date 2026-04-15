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

## Troubleshooting

- If Alembic says `Path doesn't exist: migrations`, run it from the repo root with `-c apps/api/alembic.ini`.
- If chat returns zero recommendations:
  1. Confirm the expected dataset file exists.
  2. Confirm `/api/v1/chat` is returning populated state constraints.
  3. Restart the API process if the recommendation catalog was preloaded before a data change.
  4. Verify `/api/v1/recommendations/query` independently before debugging the frontend.
- If chat returns `429`, inspect `error.code`, `Retry-After`, and `X-Trace-ID` before changing policy.

## Related Docs

- `app/README.md`
- `../../instructions/02-backend/`
- `../../instructions/04-llm-orchestrator/`
