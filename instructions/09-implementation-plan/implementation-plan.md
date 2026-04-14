# Implementation Plan

This plan is divided into two phases: MVP (midterm) and Final (production-grade demo). Each step is small, reviewable, and includes explicit doc updates.

## Phase 1: MVP (midterm)

### Epic: Repo scaffolding

#### Step 1: Create runtime repo structure and placeholders

Objective: Establish the required runtime folder structure and placeholder docs for new services.
Rationale: Ensures consistent layout before any code is added.
Preconditions: None.
Files to touch:
- [apps/api/README.md](apps/api/README.md)
- [apps/web/README.md](apps/web/README.md)
- [infra/docker/README.md](infra/docker/README.md)
- [scripts/README.md](scripts/README.md)
- [tests/README.md](tests/README.md)
Implementation tasks:
- [ ] Create `apps/`, `infra/`, `scripts/`, and `tests/` folders.
- [ ] Add placeholder READMEs describing purpose and ownership.
Commands to run:
```bash
mkdir -p apps/api apps/web infra/docker scripts tests
```
Acceptance criteria:
- All folders exist with README placeholders.
Verification:
- `ls -la apps infra scripts tests` shows new directories.
Doc updates required:
- [../01-architecture/repo-structure.md](../01-architecture/repo-structure.md)
Suggested commit message: `chore: add runtime repo scaffold`
Rollback notes: Remove the new directories and READMEs if needed.

### Epic: Backend foundation

#### Step 2: Add FastAPI app skeleton and health endpoint

Objective: Create a minimal FastAPI app with a `/health` endpoint.
Rationale: Provides a running service baseline for later additions.
Preconditions: Step 1 complete.
Files to touch:
- [apps/api/app/main.py](apps/api/app/main.py)
- [apps/api/app/api/v1/health.py](apps/api/app/api/v1/health.py)
- [apps/api/app/schemas/api/health.py](apps/api/app/schemas/api/health.py)
- [apps/api/app/services/health_status.py](apps/api/app/services/health_status.py)
- [apps/api/app/core/config.py](apps/api/app/core/config.py)
Implementation tasks:
- [ ] Initialize FastAPI app and include a router.
- [ ] Keep `api/v1/health.py` as a thin router (HTTP contract wiring only).
- [ ] Define health response schema in `schemas/api/health.py`.
- [ ] Build health payload in `services/health_status.py`.
- [ ] Add basic settings model.
Commands to run:
```bash
python -m pytest -q
```
Acceptance criteria:
- `GET /api/v1/health` returns status OK.
Verification:
- Manual curl or simple test confirms response payload.
Doc updates required:
- [../02-backend/api-design.md](../02-backend/api-design.md)
- [../02-backend/services-and-modules.md](../02-backend/services-and-modules.md)
Suggested commit message: `feat(backend): add FastAPI skeleton and health endpoint`
Rollback notes: Revert new backend app files.

#### Step 3: Configure DB session and Alembic

Objective: Set up SQLAlchemy base, DB session, and Alembic configuration.
Rationale: Required to support migrations and model creation.
Preconditions: Step 2 complete.
Files to touch:
- [apps/api/app/db/base.py](apps/api/app/db/base.py)
- [apps/api/app/db/session.py](apps/api/app/db/session.py)
- [apps/api/alembic.ini](apps/api/alembic.ini)
- [apps/api/migrations/env.py](apps/api/migrations/env.py)
Implementation tasks:
- [ ] Configure async DB session and engine.
- [ ] Initialize Alembic environment with correct metadata.
Commands to run:
```bash
alembic revision --autogenerate -m "init"
```
Acceptance criteria:
- Alembic can generate a revision without errors.
Verification:
- `alembic current` runs without failures.
Doc updates required:
- [../02-backend/migrations.md](../02-backend/migrations.md)
Suggested commit message: `chore(backend): configure SQLAlchemy and Alembic`
Rollback notes: Remove Alembic config and DB modules.

### Epic: Data model

#### Step 4: Implement core DB models and migration

Objective: Add core models for sessions, messages, catalog, embeddings, and events.
Rationale: Provides storage for runtime state and catalog.
Preconditions: Step 3 complete.
Files to touch:
- [apps/api/app/db/models/*.py](apps/api/app/db/models/*.py)
- [apps/api/migrations/versions/*.py](apps/api/migrations/versions/*.py)
Implementation tasks:
- [ ] Define models per `data-model.md`.
- [ ] Generate and review migration.
Commands to run:
```bash
alembic revision --autogenerate -m "core tables"
alembic upgrade head
```
Acceptance criteria:
- Tables exist in local DB and match the schema.
Verification:
- Query `information_schema.tables` or use SQL client.
Doc updates required:
- [../02-backend/data-model.md](../02-backend/data-model.md)
Suggested commit message: `feat(backend): add core DB models and migration`
Rollback notes: Downgrade migration to previous revision.

### Epic: Catalog ingestion

#### Step 5: Add catalog seed script and sample data

Objective: Provide a deterministic seed dataset for local dev and tests that covers hotels, restaurants, and activities.
Rationale: Required for consistent recommender outputs and tests.
Preconditions: Step 4 complete.
Files to touch:
- [scripts/seed_catalog.py](scripts/seed_catalog.py)
- [scripts/data/catalog_seed.json](scripts/data/catalog_seed.json)
Implementation tasks:
- [ ] Create a deterministic catalog dataset with hotels, restaurants, and activities.
- [ ] Implement seed script to upsert into `catalog_items`.
Commands to run:
```bash
python scripts/seed_catalog.py
```
Acceptance criteria:
- At least 50 catalog items are inserted and each item type is represented.
Verification:
- `SELECT COUNT(*) FROM catalog_items;` returns expected count.
Doc updates required:
- [../07-infra-ops/local-dev.md](../07-infra-ops/local-dev.md)
Suggested commit message: `feat(data): add catalog seed script`
Rollback notes: Delete seeded rows using a cleanup script.

### Epic: Retrieval and ranking

#### Step 6: Implement retrieval interface and pgvector retriever

Objective: Add a retrieval interface with a pgvector implementation.
Rationale: Provides candidates for ranking deterministically.
Preconditions: Step 5 complete.
Files to touch:
- [apps/api/app/services/recommender/retrieval.py](apps/api/app/services/recommender/retrieval.py)
- [apps/api/app/services/recommender/pgvector.py](apps/api/app/services/recommender/pgvector.py)
Implementation tasks:
- [ ] Define retrieval interface and candidate schema.
- [ ] Implement pgvector similarity query with hard filters (budget, dates, star rating, and location).
- [ ] Return top-K candidates (default 100–300).
Commands to run:
```bash
python -m pytest tests/recommender/test_retrieval.py -q
```
Acceptance criteria:
- Retrieval returns a stable list of candidates for a fixed query and respects top-K bounds.
Verification:
- Unit test confirms ordering and count.
Doc updates required:
- [../03-recommender/recommender-overview.md](../03-recommender/recommender-overview.md)
Suggested commit message: `feat(recommender): add retrieval interface and pgvector impl`
Rollback notes: Revert retrieval modules.

#### Step 7: Implement heuristic ranker (v1)

Objective: Implement deterministic scoring and tie-breaking per spec.
Rationale: Provides a testable ranking baseline for MVP.
Preconditions: Step 6 complete.
Files to touch:
- [apps/api/app/services/recommender/ranker.py](apps/api/app/services/recommender/ranker.py)
- [tests/recommender/test_ranker.py](tests/recommender/test_ranker.py)
Implementation tasks:
- [ ] Implement scoring formula and tie-breaks.
- [ ] Add unit tests for determinism and monotonicity behavior.
Commands to run:
```bash
python -m pytest tests/recommender/test_ranker.py -q
```
Acceptance criteria:
- Ranker outputs are deterministic and match expected scores.
Verification:
- Tests pass with fixed inputs.
Doc updates required:
- [../03-recommender/heuristic-ranker-spec.md](../03-recommender/heuristic-ranker-spec.md)
- [../03-recommender/explanations.md](../03-recommender/explanations.md)
Suggested commit message: `feat(recommender): add heuristic ranker v1`
Rollback notes: Revert ranker and tests.

#### Step 8: Compose recommendation service

Objective: Combine retrieval and ranking into a single service API.
Rationale: Provides deterministic results to orchestrator and API.
Preconditions: Step 7 complete.
Files to touch:
- [apps/api/app/services/recommender/service.py](apps/api/app/services/recommender/service.py)
- [apps/api/app/schemas/api/recommendations.py](apps/api/app/schemas/api/recommendations.py)
Implementation tasks:
- [ ] Implement service to return ranked results (top-N 10–20) and explanations.
- [ ] Include `ranking_version` in outputs.
Commands to run:
```bash
python -m pytest tests/recommender/test_service.py -q
```
Acceptance criteria:
- Service returns ranked results for a fixed query.
Verification:
- Unit test validates response structure.
Doc updates required:
- [../03-recommender/recommender-overview.md](../03-recommender/recommender-overview.md)
Suggested commit message: `feat(recommender): add recommendation service`
Rollback notes: Revert service module and schema.

### Epic: Orchestrator and tools

#### Step 9: Define session state and tool schemas

Objective: Add Pydantic schemas for session state and tool inputs/outputs.
Rationale: Enforces strict validation for LLM orchestration.
Preconditions: Step 8 complete.
Files to touch:
- [apps/api/app/schemas/state.py](apps/api/app/schemas/state.py)
- [apps/api/app/schemas/tools/*.py](apps/api/app/schemas/tools/*.py)
Implementation tasks:
- [ ] Implement session state schema.
- [ ] Implement tool input/output models.
Commands to run:
```bash
python -m pytest tests/orchestrator/test_schemas.py -q
```
Acceptance criteria:
- All schemas validate example payloads.
Verification:
- Tests pass for valid and invalid examples.
Doc updates required:
- [../04-llm-orchestrator/session-state-schema.md](../04-llm-orchestrator/session-state-schema.md)
- [../04-llm-orchestrator/tool-schemas.md](../04-llm-orchestrator/tool-schemas.md)
Suggested commit message: `feat(orchestrator): add state and tool schemas`
Rollback notes: Remove schemas and tests.

#### Step 10: Implement orchestrator service

Objective: Add the tool-first orchestrator flow.
Rationale: Core chat behavior requires validated tool orchestration.
Preconditions: Step 9 complete.
Files to touch:
- [apps/api/app/services/orchestrator/service.py](apps/api/app/services/orchestrator/service.py)
- [apps/api/app/services/orchestrator/policies.py](apps/api/app/services/orchestrator/policies.py)
Implementation tasks:
- [ ] Implement intent parsing and tool selection.
- [ ] Integrate recommender tool call.
- [ ] Handle validation errors and timeouts.
Commands to run:
```bash
python -m pytest tests/orchestrator/test_service.py -q
```
Acceptance criteria:
- Orchestrator returns a structured response for a fixed input.
Verification:
- Unit test confirms tool call and response formatting.
Doc updates required:
- [../04-llm-orchestrator/orchestrator-overview.md](../04-llm-orchestrator/orchestrator-overview.md)
- [../04-llm-orchestrator/prompts-and-guardrails.md](../04-llm-orchestrator/prompts-and-guardrails.md)
Suggested commit message: `feat(orchestrator): add tool-first orchestration`
Rollback notes: Revert orchestrator service files.

### Epic: API endpoints

#### Step 11: Add chat endpoint

Objective: Expose `/api/v1/chat` with session persistence.
Rationale: Enables frontend integration for MVP.
Preconditions: Step 10 complete.
Files to touch:
- [apps/api/app/api/v1/chat.py](apps/api/app/api/v1/chat.py)
- [apps/api/app/schemas/api/chat.py](apps/api/app/schemas/api/chat.py)
- [apps/api/app/repositories/chat.py](apps/api/app/repositories/chat.py)
- [apps/api/app/services/chat_uow.py](apps/api/app/services/chat_uow.py)
- [apps/api/app/services/chat_persistence.py](apps/api/app/services/chat_persistence.py)
- [apps/api/app/api/v1/__init__.py](apps/api/app/api/v1/__init__.py)
Implementation tasks:
- [ ] Keep `api/v1/chat.py` as a thin router (dependency wiring + orchestration call only).
- [ ] Define chat request/response schemas in `schemas/api/chat.py`.
- [ ] Extract chat data access to a targeted repository in `repositories/chat.py`.
- [ ] Add chat-specific unit-of-work transaction handling in `services/chat_uow.py`.
- [ ] Keep session identity/state validation helpers in `services/chat_persistence.py`.
- [ ] Wire repository + unit of work, state persistence, and response mapping in the endpoint.
Commands to run:
```bash
python -m pytest tests/api/test_chat.py -q
```
Acceptance criteria:
- Chat endpoint returns assistant message and recommendations for hotels, restaurants, and activities.
Verification:
- Integration test passes with seeded data.
Doc updates required:
- [../02-backend/api-design.md](../02-backend/api-design.md)
- [../02-backend/services-and-modules.md](../02-backend/services-and-modules.md)
- [../01-architecture/system-overview.md](../01-architecture/system-overview.md)
Suggested commit message: `feat(api): add chat endpoint`
Rollback notes: Remove endpoint and related tests.

#### Step 12: Add recommendations endpoint

Objective: Expose `/api/v1/recommendations/query` for direct access.
Rationale: Useful for debugging and integration tests.
Preconditions: Step 11 complete.
Files to touch:
- [apps/api/app/api/v1/recommendations.py](apps/api/app/api/v1/recommendations.py)
- [apps/api/app/schemas/api/recommendations.py](apps/api/app/schemas/api/recommendations.py)
- [apps/api/app/services/recommendation_query.py](apps/api/app/services/recommendation_query.py)
Implementation tasks:
- [ ] Keep `api/v1/recommendations.py` as a thin router (DI + HTTP error mapping).
- [ ] Define API request/response schemas in `schemas/api/recommendations.py`.
- [ ] Execute recommendation tool and validate tool payloads in `services/recommendation_query.py`.
- [ ] Return ranked results with version.
Commands to run:
```bash
python -m pytest tests/api/test_recommendations.py -q
```
Acceptance criteria:
- Endpoint returns deterministic results.
Verification:
- Tests pass and results match ranker spec.
Doc updates required:
- [../02-backend/api-design.md](../02-backend/api-design.md)
- [../02-backend/services-and-modules.md](../02-backend/services-and-modules.md)
Suggested commit message: `feat(api): add recommendations query endpoint`
Rollback notes: Remove endpoint and tests.

#### Step 13: Add events endpoint with idempotency

Objective: Provide `/api/v1/events` ingestion with validation and idempotency.
Rationale: Required for analytics and evaluation.
Preconditions: Step 12 complete.
Files to touch:
- [apps/api/app/api/v1/events.py](apps/api/app/api/v1/events.py)
- [apps/api/app/services/events/service.py](apps/api/app/services/events/service.py)
Implementation tasks:
- [ ] Validate event payloads.
- [ ] Enforce idempotency keys.
Commands to run:
```bash
python -m pytest tests/api/test_events.py -q
```
Acceptance criteria:
- Duplicate events are rejected with 409.
Verification:
- Integration tests validate idempotency behavior.
Doc updates required:
- [../06-events-analytics/event-taxonomy.md](../06-events-analytics/event-taxonomy.md)
- [../02-backend/api-design.md](../02-backend/api-design.md)
Suggested commit message: `feat(api): add events ingestion with idempotency`
Rollback notes: Remove events endpoint and service.

### Epic: Frontend MVP

#### Step 14: Scaffold React app and API client

Objective: Initialize frontend with Vite and a typed API client, then deliver a homepage-first UI baseline.
Rationale: Provides UI foundation for MVP flows.
Preconditions: Step 11 complete.
Files to touch:
- [apps/web/package.json](apps/web/package.json)
- [apps/web/src/api/client.ts](apps/web/src/api/client.ts)
- [apps/web/src/App.tsx](apps/web/src/App.tsx)
- [apps/web/src/pages/HomePage.tsx](apps/web/src/pages/HomePage.tsx)
- [apps/web/src/styles.css](apps/web/src/styles.css)
Implementation tasks:
- [ ] Create Vite React app.
- [ ] Add API client with base URL and types.
- [ ] Build a responsive homepage with strong visual hierarchy and clear planner CTA.
- [ ] Show API health status on the homepage using `/api/v1/health`.
- [ ] Add standalone informational routes for `Why TravelTom` and `How It Works` to support pre-chat orientation.
Commands to run:
```bash
npm install
npm run dev
```
Acceptance criteria:
- Frontend starts locally and renders a homepage suitable as the MVP entry surface.
Verification:
- Browser shows the app without errors.
Doc updates required:
- [../05-frontend/frontend-architecture.md](../05-frontend/frontend-architecture.md)
- [../05-frontend/ux-flows.md](../05-frontend/ux-flows.md)
Suggested commit message: `feat(frontend): scaffold React app with API client`
Rollback notes: Remove frontend scaffold.

#### Step 15: Implement chat UI and message flow

Objective: Add chat UI with message list and input.
Rationale: Core user interaction for TravelTom.
Preconditions: Step 14 complete.
Files to touch:
- [apps/web/src/components/ChatView.tsx](apps/web/src/components/ChatView.tsx)
- [apps/web/src/store/session.ts](apps/web/src/store/session.ts)
Implementation tasks:
- [ ] Implement message list and input.
- [ ] Call `/api/v1/chat` and append response.
- [ ] Add a planner route surface for chat (`/planner`) and wire navigation to it.
- [ ] Add loading, error, and retry UI states for chat sends.
Commands to run:
```bash
npm run test
```
Acceptance criteria:
- User can send a message and see assistant response.
Verification:
- Manual test confirms message flow.
Doc updates required:
- [../05-frontend/frontend-architecture.md](../05-frontend/frontend-architecture.md)
- [../05-frontend/ux-flows.md](../05-frontend/ux-flows.md)
Suggested commit message: `feat(frontend): add chat UI and flow`
Rollback notes: Revert chat components and store.

#### Step 16: Add recommendations panel

Objective: Render recommendations with explanations and ranking for hotels, restaurants, and activities.
Rationale: Visualizes deterministic output from recommender.
Preconditions: Step 15 complete.
Files to touch:
- [apps/web/src/components/RecommendationsPanel.tsx](apps/web/src/components/RecommendationsPanel.tsx)
Implementation tasks:
- [ ] Render recommendation cards from chat response by item type.
- [ ] Show score, rank, and explanation.
Commands to run:
```bash
npm run dev
```
Acceptance criteria:
- Recommendations display correctly for a chat response and are grouped or filterable by type.
Verification:
- Manual test with seeded backend data.
Doc updates required:
- [../05-frontend/ux-flows.md](../05-frontend/ux-flows.md)
Suggested commit message: `feat(frontend): add recommendations panel`
Rollback notes: Remove panel component.

#### Step 17: Add shortlist and itinerary views

Objective: Implement shortlist management and itinerary view.
Rationale: Supports user planning workflow.
Preconditions: Step 16 complete.
Files to touch:
- [apps/web/src/components/ShortlistView.tsx](apps/web/src/components/ShortlistView.tsx)
- [apps/web/src/components/ItineraryView.tsx](apps/web/src/components/ItineraryView.tsx)
Implementation tasks:
- [ ] Allow save/remove from shortlist.
- [ ] Add a basic compare view for shortlisted items.
- [ ] Render itinerary from backend response.
Commands to run:
```bash
npm run dev
```
Acceptance criteria:
- Items can be saved to and removed from shortlist, and compared in a basic view.
Verification:
- Manual test confirms shortlist persistence during session.
Doc updates required:
- [../05-frontend/ux-flows.md](../05-frontend/ux-flows.md)
Suggested commit message: `feat(frontend): add shortlist and itinerary views`
Rollback notes: Remove shortlist and itinerary components.

#### Step 18: Add booking stub and event tracking

Objective: Add booking stub UI and fire analytics events.
Rationale: Required for funnel tracking and demo.
Preconditions: Step 17 complete.
Files to touch:
- [apps/web/src/components/BookingStub.tsx](apps/web/src/components/BookingStub.tsx)
- [apps/web/src/analytics/trackEvent.ts](apps/web/src/analytics/trackEvent.ts)
Implementation tasks:
- [ ] Implement booking CTA and confirmation state.
- [ ] Send events to `/api/v1/events`.
Commands to run:
```bash
npm run dev
```
Acceptance criteria:
- Booking CTA triggers event ingestion.
Verification:
- Event appears in backend `events` table.
Doc updates required:
- [../06-events-analytics/event-taxonomy.md](../06-events-analytics/event-taxonomy.md)
Suggested commit message: `feat(frontend): add booking stub and analytics`
Rollback notes: Remove booking stub and analytics helper.

### Epic: Observability and testing

#### Step 19: Add structured logging and tracing

Objective: Implement JSON logging and OpenTelemetry tracing.
Rationale: Required for latency and error visibility.
Preconditions: Step 13 complete.
Files to touch:
- [apps/api/app/core/logging.py](apps/api/app/core/logging.py)
- [apps/api/app/core/telemetry.py](apps/api/app/core/telemetry.py)
- [apps/api/app/main.py](apps/api/app/main.py)
Implementation tasks:
- [ ] Add logging middleware and trace ID propagation.
- [ ] Instrument chat and recommendation spans.
Commands to run:
```bash
python -m pytest tests/api/test_chat.py -q
```
Acceptance criteria:
- Logs include `trace_id` and request metadata.
Verification:
- Manual request shows structured JSON logs.
Doc updates required:
- [../07-infra-ops/observability.md](../07-infra-ops/observability.md)
Suggested commit message: `feat(obs): add structured logging and tracing`
Rollback notes: Remove logging middleware and instrumentation.

#### Step 20: Add baseline test suite and fixtures

Objective: Provide baseline unit and integration tests with fixtures.
Rationale: Ensures deterministic behavior across services.
Preconditions: Step 19 complete.
Files to touch:
- [tests/fixtures/catalog.json](tests/fixtures/catalog.json)
- [tests/recommender/*.py](tests/recommender/*.py)
- [tests/api/*.py](tests/api/*.py)
Implementation tasks:
- [ ] Add fixtures and test helpers (hotels, restaurants, activities).
- [ ] Implement unit tests for ranker and retrieval for the supported recommendation types.
Commands to run:
```bash
python -m pytest -q
```
Acceptance criteria:
- All tests pass and cover deterministic ranking.
Verification:
- CI-equivalent run passes locally.
Doc updates required:
- [../08-quality/testing-strategy.md](../08-quality/testing-strategy.md)
Suggested commit message: `test: add baseline recommender and API tests`
Rollback notes: Remove tests and fixtures.

### Epic: Local dev and CI

#### Step 21: Add Docker Compose for Postgres + pgvector

Objective: Provide local infrastructure for DB and vector search.
Rationale: Required to run MVP end-to-end locally.
Preconditions: Step 4 complete.
Files to touch:
- [infra/docker/docker-compose.yml](infra/docker/docker-compose.yml)
Implementation tasks:
- [ ] Define Postgres service with pgvector extension.
- [ ] Add API service container (optional for local dev parity).
- [ ] Add volume for persistent data.
Commands to run:
```bash
docker compose -f infra/docker/docker-compose.yml up -d
```
Acceptance criteria:
- Postgres starts and pgvector extension is available.
Verification:
- `CREATE EXTENSION IF NOT EXISTS vector;` succeeds.
Doc updates required:
- [../07-infra-ops/local-dev.md](../07-infra-ops/local-dev.md)
Suggested commit message: `chore(infra): add docker compose for local DB`
Rollback notes: Remove docker-compose file.

#### Step 22: Add minimal CI pipeline

Objective: Add CI steps for linting, type-checking, and tests.
Rationale: Ensures quality gates are enforced.
Preconditions: Step 20 complete.
Files to touch:
- [.github/workflows/ci.yml](.github/workflows/ci.yml)
Implementation tasks:
- [ ] Add CI job for backend and frontend checks.
- [ ] Configure caching for dependencies.
Commands to run:
```bash
python -m pytest -q
npm run lint
```
Acceptance criteria:
- CI pipeline runs successfully on main branch.
Verification:
- CI status is green for the workflow.
Doc updates required:
- [../08-quality/ci-cd.md](../08-quality/ci-cd.md)
Suggested commit message: `ci: add minimal lint and test pipeline`
Rollback notes: Remove CI workflow.

## Phase 2: Final (production-grade demo)

### Epic: Retrieval upgrade

#### Step 23: Add retrieval abstraction and Azure AI Search adapter

Objective: Support Azure AI Search retrieval via configuration.
Rationale: Required for final scalability and ranking.
Preconditions: Phase 1 complete.
Files to touch:
- [apps/api/app/services/recommender/retrieval.py](apps/api/app/services/recommender/retrieval.py)
- [apps/api/app/services/recommender/azure_search.py](apps/api/app/services/recommender/azure_search.py)
Implementation tasks:
- [ ] Implement Azure AI Search client.
- [ ] Switch via configuration flag.
Commands to run:
```bash
python -m pytest tests/recommender/test_retrieval.py -q
```
Acceptance criteria:
- Retrieval backend can be switched without code changes.
Verification:
- Integration test confirms backend selection.
Doc updates required:
- [../03-recommender/recommender-overview.md](../03-recommender/recommender-overview.md)
- [../01-architecture/adr/0005-vector-search-abstraction.md](../01-architecture/adr/0005-vector-search-abstraction.md)
Suggested commit message: `feat(retrieval): add Azure AI Search adapter`
Rollback notes: Disable Azure adapter and use pgvector.

### Epic: ML ranker

#### Step 24: Implement ML ranker training pipeline

Objective: Add model training and evaluation scripts for ranking.
Rationale: Enables production-grade ranking improvements.
Preconditions: Step 23 complete.
Files to touch:
- [scripts/train_ranker.py](scripts/train_ranker.py)
- [scripts/evaluate_ranker.py](scripts/evaluate_ranker.py)
- [apps/api/app/services/recommender/ml_ranker.py](apps/api/app/services/recommender/ml_ranker.py)
Implementation tasks:
- [ ] Implement training pipeline with LightGBM.
- [ ] Add evaluation metrics reporting.
Commands to run:
```bash
python scripts/train_ranker.py
python scripts/evaluate_ranker.py
```
Acceptance criteria:
- Training produces a model artifact and evaluation report.
Verification:
- Report includes NDCG@K and MAP@K.
Doc updates required:
- [../03-recommender/evaluation.md](../03-recommender/evaluation.md)
Suggested commit message: `feat(recommender): add ML ranker training and eval`
Rollback notes: Revert ML scripts and model loader.

#### Step 25: Add model versioning and loading

Objective: Support model versioning and runtime loading.
Rationale: Allows safe updates and rollbacks of ranking models.
Preconditions: Step 24 complete.
Files to touch:
- [apps/api/app/services/recommender/model_registry.py](apps/api/app/services/recommender/model_registry.py)
- [apps/api/app/services/recommender/service.py](apps/api/app/services/recommender/service.py)
Implementation tasks:
- [ ] Add a model registry with version metadata.
- [ ] Load model by configured version.
Commands to run:
```bash
python -m pytest tests/recommender/test_ml_ranker.py -q
```
Acceptance criteria:
- Model version can be switched via config.
Verification:
- Tests confirm correct model selection.
Doc updates required:
- [../03-recommender/recommender-overview.md](../03-recommender/recommender-overview.md)
Suggested commit message: `feat(recommender): add model registry and versioning`
Rollback notes: Restore heuristic-only ranking.

### Epic: Event pipeline

#### Step 26: Add Event Hub streaming

Objective: Stream events to Event Hub in addition to DB.
Rationale: Supports production analytics and ML training data.
Preconditions: Step 13 complete.
Files to touch:
- [apps/api/app/services/events/streaming.py](apps/api/app/services/events/streaming.py)
- [infra/azure/eventhub.bicep](infra/azure/eventhub.bicep)
Implementation tasks:
- [ ] Implement Event Hub producer.
- [ ] Dual-write events with retry handling.
Commands to run:
```bash
python -m pytest tests/events/test_streaming.py -q
```
Acceptance criteria:
- Events are persisted in DB and published to Event Hub.
Verification:
- Integration test with mock Event Hub succeeds.
Doc updates required:
- [../06-events-analytics/event-pipeline.md](../06-events-analytics/event-pipeline.md)
Suggested commit message: `feat(events): add event streaming to Event Hub`
Rollback notes: Disable streaming feature flag.

### Epic: Security hardening

#### Step 27: Add authentication and rate limiting

Objective: Secure endpoints with auth and enforce rate limits.
Rationale: Required for production-grade demo.
Preconditions: Step 22 complete.
Files to touch:
- [apps/api/app/core/security.py](apps/api/app/core/security.py)
- [apps/api/app/api/v1/*](apps/api/app/api/v1/*)
Implementation tasks:
- [ ] Add auth middleware (Azure AD B2C over OIDC).
- [ ] Apply rate limiting to chat and events endpoints.
Commands to run:
```bash
python -m pytest tests/api/test_auth.py -q
```
Acceptance criteria:
- Unauthorized requests are rejected.
Verification:
- Tests confirm auth and rate limiting behavior.
Doc updates required:
- [../02-backend/security.md](../02-backend/security.md)
Suggested commit message: `feat(security): add auth and rate limiting`
Rollback notes: Disable auth middleware.

### Epic: Observability and ops

#### Step 28: Add App Insights dashboards and SLOs

Objective: Provide production telemetry dashboards and SLOs.
Rationale: Enables monitoring of latency and errors.
Preconditions: Step 19 complete.
Files to touch:
- [infra/azure/appinsights.bicep](infra/azure/appinsights.bicep)
- [infra/azure/dashboards.json](infra/azure/dashboards.json)
Implementation tasks:
- [ ] Add App Insights resource.
- [ ] Create dashboard for P95 latency and errors.
Commands to run:
```bash
az deployment group create -f infra/azure/appinsights.bicep
```
Acceptance criteria:
- Dashboards show live metrics in Azure.
Verification:
- Manual verification in Azure portal.
Doc updates required:
- [../07-infra-ops/observability.md](../07-infra-ops/observability.md)
Suggested commit message: `chore(obs): add App Insights dashboards`
Rollback notes: Remove Azure resources.

#### Step 29: Add production deployment scripts

Objective: Provide infra-as-code for full deployment.
Rationale: Required for final demo.
Preconditions: Step 28 complete.
Files to touch:
- [infra/azure/main.bicep](infra/azure/main.bicep)
- [infra/azure/README.md](infra/azure/README.md)
Implementation tasks:
- [ ] Provision Container Apps, Postgres, AI Search, Event Hub.
- [ ] Document deployment steps.
Commands to run:
```bash
az deployment group create -f infra/azure/main.bicep
```
Acceptance criteria:
- Deployment completes without errors.
Verification:
- Services are reachable and healthy.
Doc updates required:
- [../07-infra-ops/deployment-final.md](../07-infra-ops/deployment-final.md)
Suggested commit message: `chore(infra): add Azure deployment scripts`
Rollback notes: Delete resource group.

### Epic: Final testing

#### Step 30: Add E2E tests and performance checks

Objective: Validate end-to-end flows and latency targets.
Rationale: Ensures readiness for final demo.
Preconditions: Step 29 complete.
Files to touch:
- [tests/e2e/*.ts](tests/e2e/*.ts)
- [scripts/perf_check.py](scripts/perf_check.py)
Implementation tasks:
- [ ] Add E2E tests for chat and recommendations.
- [ ] Add P95 latency checks.
Commands to run:
```bash
npm run test:e2e
python scripts/perf_check.py
```
Acceptance criteria:
- E2E tests pass.
- P95 latency under 2 seconds for chat on local environment.
Verification:
- Test reports show pass and latency metrics.
Doc updates required:
- [../08-quality/testing-strategy.md](../08-quality/testing-strategy.md)
Suggested commit message: `test: add e2e tests and perf checks`
Rollback notes: Remove E2E tests and perf script.
