# TravelTom.ai

TravelTom is a full-stack travel planning app with a deterministic recommendation
core and an optional LLM-assisted chat layer. The backend owns recommendation
execution, state updates, and safety checks; provider-backed planning and
response composition are bounded helpers, not sources of truth.

## What This Repo Is

TravelTom delivers a travel-planning chat experience backed by deterministic
retrieval and ranking. Recommendations are grounded in validated backend data,
and the conversational layer is designed to stay correct even when LLM support
is disabled or degraded.

## Highlights

- Deterministic recommendations with ranking explanations.
- Backend-owned chat orchestration with strict state validation.
- Optional provider-assisted planning and grounded response composition.
- Clean separation between orchestration and recommendation logic.
- First-class documentation in `instructions/`.
- Local-first development with Docker, Alembic, seed data, and smoke tooling.
- Azure deployment scaffolding for Container Apps, PostgreSQL, Key Vault, and App Insights.

## Runtime Shape

- `apps/api`: FastAPI backend, chat persistence, recommender, auth, telemetry.
- `apps/web`: React/Vite frontend.
- `traveltom/recommendor`: deterministic ranking and ML ranker experiments.
- `instructions/`: repo source-of-truth docs.
- `scripts/`: seed, evaluation, and smoke tooling.

## Chat Architecture

- `/api/v1/chat` runs through a deterministic orchestrator.
- The backend decides when to clarify, when to search, and how to build
  `RecommendationQuery`.
- The LLM, when enabled, is limited to:
  - structured planner hints
  - grounded response composition
- `/api/v1/recommendations/query` is deterministic end to end.

## Local Backend Quickstart

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

## Local Chat Modes

- Default local mode: `ORCHESTRATOR_LLM_PROVIDER=ollama`
- Deterministic-only mode: `ORCHESTRATOR_LLM_PROVIDER=disabled`
- OpenAI mode: `ORCHESTRATOR_LLM_PROVIDER=openai`

The active recommendation runtime reads from seeded PostgreSQL `catalog_items`.
`RECOMMENDER_DATASET_PATH` is not used by `/api/v1/chat` or
`/api/v1/recommendations/query`; it remains an offline or legacy setting.

## Recommender Runtime

- Active API runtime: `traveltom/recommendor/recommendor_v1.py`
- Runtime data source: PostgreSQL `catalog_items`
- Shared runtime adapter: `apps/api/app/services/recommendation_runtime.py`
- Deterministic direct endpoint: `/api/v1/recommendations/query`

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

## Repository Layout

- `apps/` runtime services (API + web).
- `infra/` local and cloud infrastructure.
- `scripts/` data and tooling.
- `tests/` unit and integration tests.
- `instructions/` authoritative design and implementation docs.
- `traveltom/` recommender and experiment code.

## Docs Map

- Start here: `instructions/README.md`
- Backend modules: `instructions/02-backend/`
- Recommender runtime: `instructions/03-recommender/`
- Chat orchestration: `instructions/04-llm-orchestrator/`
- Frontend UX: `instructions/05-frontend/`
- Local dev and ops: `instructions/07-infra-ops/`
- Testing strategy: `instructions/08-quality/testing-strategy.md`
- Azure runtime infra: `infra/azure/README.md`

## Deployment

- Production API container: `apps/api/Dockerfile`
- Production web container: `apps/web/Dockerfile`
- Azure infra modules: `infra/azure/`
- Smoke checks:
  - `pwsh ./scripts/smoke-api.ps1 -BaseUrl https://<api-url>`
  - `pwsh ./scripts/smoke-web.ps1 -BaseUrl https://<web-url>`
  - `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl https://<api-url> -Provider ollama`

## Configuration Rules

- Never hard-code environment-specific values in code.
- Store local settings in `.env` and keep `.env.example` updated.

## Status

MVP build-out in progress.

## License

See `LICENSE`.
