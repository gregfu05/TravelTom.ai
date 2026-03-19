# TravelTom.ai

Plan trips faster with a deterministic, tool-first travel planner. TravelTom combines a strict recommender pipeline with an orchestration layer so results are explainable, testable, and reproducible.

**What This Repo Is**
TravelTom is a full-stack project that delivers a travel-planning chat experience backed by a deterministic retrieval + ranking system. The LLM orchestrates tools but never fabricates recommendations.

**Highlights**
- Deterministic recommendations with ranking explanations.
- Strict schemas and validation for tool calls and responses.
- Clean separation between orchestration and recommendation logic.
- First-class documentation in `instructions/` with an executable plan.
- Local-first development with Docker, Alembic, and seed data.

**Architecture (MVP)**
- API service in `apps/api` using FastAPI.
- Recommender service (retrieval + ranking) in `apps/api/app/services/recommender`.
- Orchestrator service in `apps/api/app/services/orchestrator`.
- Frontend in `apps/web` (Vite + React).
- Analytics events in `apps/api/app/services/events`.

**Quickstart (Backend)**
1. Create and activate a virtual environment.
2. Install dependencies.
3. Configure `.env`.
4. Run migrations.
5. Build cleaned catalog snapshot.
6. Seed catalog data.
7. Start the API.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

```bash
cp .env.example .env
```

```bash
alembic -c apps/api/alembic.ini upgrade head
```

```bash
python -m traveltom.cleaning.cleaning
```

Optional (legacy SB dataset): `scripts/seed_catalog.py` manages the legacy
Santa Barbara sample. The active recommender v2 instead reads
`traveltom/datasets/cleaned_Yelp_DS.parquet` directly (no DB seed required).

```bash
uvicorn app.main:app --reload --app-dir apps/api
```

**Recommender v2 (current)**
- Code: `traveltom/recommendor/recommendor_v2.py`
- Data: `traveltom/datasets/cleaned_Yelp_DS.parquet`
- Defaults to top 5 results (1–10 allowed, capped at 10).
- Filters user intents (bars, burgers, late night, parking, wifi, etc.), ranks with
  `score = stars + 0.25 * log1p(review_count) + 0.25 * popularity`, returns place
  name + Google Maps link.

**Repository Layout**
- `apps/` runtime services (API + web).
- `infra/` local and cloud infrastructure.
- `scripts/` data and tooling.
- `tests/` unit and integration tests.
- `instructions/` authoritative design and implementation plan.
- `traveltom/` existing prototypes and experiments.

**Docs Map**
- Start here: `instructions/README.md`.
- Implementation plan: `instructions/09-implementation-plan/implementation-plan.md`.
- Backend design: `instructions/02-backend/`.
- Recommender design: `instructions/03-recommender/`.
- Orchestrator design: `instructions/04-llm-orchestrator/`.
- Frontend UX: `instructions/05-frontend/`.

**Configuration Rules**
- Never hard-code environment-specific values in code.
- Store local settings in `.env` and keep `.env.example` updated.

**Status**
MVP build-out in progress.

**License**
See `LICENSE`.
