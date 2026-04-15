# TravelTom.ai

TravelTom is a full-stack travel planning app with a deterministic recommendation
core and an optional LLM-assisted chat layer. The backend owns recommendation
execution, state updates, and safety checks; provider-backed planning and
response composition are bounded helpers, not sources of truth.

## Runtime shape

- `apps/api`: FastAPI backend, chat persistence, recommender, auth, telemetry.
- `apps/web`: React/Vite frontend.
- `traveltom/recommendor`: deterministic ranking and ML ranker experiments.
- `instructions/`: repo source-of-truth docs.
- `scripts/`: seed, evaluation, and smoke tooling.

## Chat architecture

- `/api/v1/chat` runs through a deterministic orchestrator.
- The backend decides when to clarify, when to search, and how to build
  `RecommendationQuery`.
- The LLM, when enabled, is limited to:
  - structured planner hints
  - grounded response composition
- `/api/v1/recommendations/query` is deterministic end to end.

## Local backend quickstart

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Run Postgres and migrations.
5. Seed `catalog_items`.
6. Start the API.

```bash
python -m venv venv
venv\Scripts\activate
pip install -e .
copy .env.example .env
alembic -c apps/api/alembic.ini upgrade head
python scripts/seed_catalog.py --truncate
uvicorn app.main:app --reload --app-dir apps/api
```

## Local chat modes

- Default local mode: `ORCHESTRATOR_LLM_PROVIDER=ollama`
- Deterministic-only mode: `ORCHESTRATOR_LLM_PROVIDER=disabled`
- OpenAI mode: `ORCHESTRATOR_LLM_PROVIDER=openai`

The active recommendation runtime reads from seeded PostgreSQL `catalog_items`.
`RECOMMENDER_DATASET_PATH` is not used by `/api/v1/chat` or
`/api/v1/recommendations/query`; it remains an offline/legacy setting.

## Verification

Run the backend test suite:

```bash
venv\Scripts\python.exe -m pytest tests -q
```

Run smoke checks against a running API:

```bash
pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000
pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled
pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama
```

## Docs map

- Backend modules: `instructions/02-backend/`
- Recommender runtime: `instructions/03-recommender/`
- Chat orchestration: `instructions/04-llm-orchestrator/`
- Local dev and ops: `instructions/07-infra-ops/`
- Testing strategy: `instructions/08-quality/testing-strategy.md`

## License

See `LICENSE`.
