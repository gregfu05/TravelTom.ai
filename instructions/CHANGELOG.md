# Instructions Changelog

## 2026-02-26

- Refactored `apps/api/app/api/v1/chat.py` into a thin router by extracting:
  - Chat API Pydantic schemas (`ChatRequest`, `ChatResponse`, `ChatRecommendation`,
    `ClientContext`) into `apps/api/app/schemas/api/chat.py`.
  - Session/message/recommendation persistence helpers (`get_or_create_session`,
    `load_session_state`, `persist_messages`, `persist_recommendation_snapshot`,
    `session_pk`, `parse_optional_uuid`) into `apps/api/app/services/chat_persistence.py`.
- Added `schemas/api/` package (`__init__.py`) per the suggested FastAPI layout.
- Updated `02-backend/services-and-modules.md`: added `chat_persistence.py` to layout
  and module boundaries; added `schemas/api/chat.py` to layout.
- Updated `02-backend/api-design.md`: chat endpoint implementation notes now reference
  the new schema and persistence file locations.
- Updated `09-implementation-plan/implementation-plan.md` Step 11 to include
  `schemas/api/chat.py` and `services/chat_persistence.py` in files/tasks, and
  linked `02-backend/services-and-modules.md` in required doc updates.
- Refactored remaining API routers to the same thin-endpoint style:
  - `apps/api/app/api/v1/health.py` now delegates payload construction to
    `apps/api/app/services/health_status.py` and uses
    `apps/api/app/schemas/api/health.py`.
  - `apps/api/app/api/v1/recommendations.py` now delegates tool execution and
    validation to `apps/api/app/services/recommendation_query.py` and uses
    `apps/api/app/schemas/api/recommendations.py`.
- Updated `02-backend/services-and-modules.md` and `02-backend/api-design.md`
  to document thin-router boundaries for health and recommendations.
- Updated `09-implementation-plan/implementation-plan.md` Step 2 and Step 12
  files/tasks to match the extracted schema/service modules.
- Implemented targeted persistence patterns for chat:
  - Added `apps/api/app/repositories/chat.py` with a feature-specific
    `ChatRepository` (session lookup/creation, message writes, recommendation snapshots).
  - Added `apps/api/app/services/chat_uow.py` with `ChatUnitOfWork` for
    request-scoped transaction boundaries.
  - Updated `apps/api/app/api/v1/chat.py` to use repository + unit-of-work
    instead of direct session operations.
  - Reduced `apps/api/app/services/chat_persistence.py` to session identity/state
    helper responsibilities.
- Updated architecture/docs to reflect repository + UoW boundaries:
  - `01-architecture/system-overview.md`
  - `02-backend/services-and-modules.md`
  - `02-backend/api-design.md`
  - `09-implementation-plan/implementation-plan.md` (Step 11)
  - `apps/api/README.md`

## 2026-02-24

- Updated `05-frontend/frontend-architecture.md` to reflect the planner split
  chat + recommendations rail layout that keeps chat visible while picks are
  present.
- Updated `05-frontend/ux-flows.md` with constrained-height recommendation rail
  behavior, internal scrolling, and the `Show/Hide picks` interaction.

## 2026-02-23

- Updated `05-frontend/frontend-architecture.md` to reflect implemented
  planner behavior: chat + recommendations rendering from `/api/v1/chat`, and
  current Zustand session state fields.
- Updated `05-frontend/ux-flows.md` to document recommendation rendering in the
  primary planner flow and current recommendations panel behavior.
- Updated `07-infra-ops/local-dev.md` troubleshooting with a frontend-specific
  check for chat responses that include recommendations but no rendered cards.
- Updated `03-recommender/recommender-overview.md` to reflect DB-backed
  catalog retrieval (`catalog_items`) for the minimal recommender flow.
- Updated `07-infra-ops/local-dev.md` first-run and troubleshooting guidance to
  use cleaned snapshot seeding as the recommender input path.
- Documented recommender runtime fix for thread/event-loop-safe DB reads and
  added troubleshooting verification with `/api/v1/recommendations/query`.
- Updated recommender runtime behavior to auto-refresh cached catalog snapshot
  after empty reads to avoid stale-empty cache after seeding.
- Updated frontend/local-dev docs with explicit Vite proxy target configuration
  via `apps/web/.env` (`VITE_API_PROXY_TARGET`) to avoid calling stale backend
  instances on the wrong port.
- Added deterministic orchestrator state extraction module
  (`apps/api/app/services/orchestrator/extraction.py`) and wired extraction into
  chat orchestration before policy routing and recommendation tool calls.
- Updated recommender runtime to apply destination hard-filtering from
  `RecommendationQuery.constraints.destination` and return empty results when no
  destination rows match.
- Added backend and infra troubleshooting guidance for validating populated
  `state.constraints` in `/api/v1/chat` responses.
- Fixed recommender keyword false-positive matching so `bar` no longer matches
  inside location names like `Santa Barbara`.
- Added request-level `item_type` filter extraction in orchestrator and applied
  hard item-type filtering in recommender (`destination|hotel|flight`).
- Added hotel-result quality narrowing to prefer lodging-tagged rows over
  generic travel/tour rows for hotel queries.
- Updated seed classification rules to avoid mapping generic `Hotels & Travel`
  categories to `hotel` without lodging-specific tags.
- Reduced chat orchestrator recommendation count to top 5 per message for
  cleaner planner output.
- Redesigned planner recommendations panel to a compact top-5 list with
  metadata badges and collapsible "Why this pick" details.
- Updated mypy project configuration to exclude generated build/dist/egg-info
  paths and avoid duplicate-module failures when running `mypy .`.
- Added `scripts/__init__.py` so `scripts.seed_catalog` resolves as a single
  module namespace under mypy.

## 2026-02-12

- Added `04-llm-orchestrator/chatbot-orchestration-skill.md` defining the chatbot/orchestration implementation skill and quality bar.
- Updated `04-llm-orchestrator/session-state-schema.md` to match implemented Pydantic models in `apps/api/app/schemas/state.py`.
- Updated `04-llm-orchestrator/tool-schemas.md` to match implemented tool contracts in `apps/api/app/schemas/tools/*`.
- Linked the new skill doc from `04-llm-orchestrator/orchestrator-overview.md`.
- Updated orchestrator instructions for Step 10 with implemented policy routing, timeout handling, and placeholder recommendation behavior.
- Updated prompt/guardrail instructions with explicit fallback requirements for invalid inputs, tool timeouts, invalid tool payloads, and empty results.
- Updated `02-backend/api-design.md` with Step 11 chat endpoint implementation notes, persistence behavior, and FastAPI 422 validation status.
- Added Step 12 recommendation query endpoint notes in `02-backend/api-design.md`, including schema-validation behavior and placeholder-mode empty results.
- Refactored orchestrator service to LangChain-style `StructuredTool` + `RunnableLambda` execution flow with compatibility shim for local environments without `langchain-core`.
- Updated orchestrator docs and skill instructions to reflect active LangChain integration.

## 2026-02-06

- Converted `OPEN_QUESTIONS.md` to active provisional decisions with a lock timestamp.
- Fixed recommender decisions: in-process runtime, LightGBM model family, Azure AI Search primary with pgvector fallback, Azure ML Registry.
- Added explicit evaluation gates, retraining cadence, retraining triggers, and required training artifacts.
- Locked final deployment target to Azure Container Apps and documented blue-green rollout and rollback behavior.
- Added budget-mode constraints with a USD 10/month cloud spend cap.
- Added model drift checks, thresholds, and alert ownership in observability docs.
- Added ML CI/CD promotion gates, manifest requirements, and reviewer approvals.
- Fixed event pipeline and taxonomy ambiguity (mandatory final dual-write, explicit `message_id` requirements, deletion SLA).
- Locked final auth provider path to Azure AD B2C and added secret rotation and access rules.
- Updated implementation plan wording to LightGBM and Azure AD B2C.
- Added explicit Zen of Python enforcement rules and Python PR checklist in `08-quality/code-standards.md`.
- Added Zen of Python compliance requirement to coding-agent rules and quality gates in `README.md`.
- Updated event data-model documentation to require `session_id` and scoped idempotency uniqueness.

## 2026-02-04

- Updated documentation to align with `TravelTom_Final_Design_Document.pdf` (requirements, architecture, recommender, orchestrator, events, and plan).
- Adjusted repo structure to `apps/api` and `apps/web` and updated paths across the plan.
- Refined recommender specs with retrieval sizes, ranking signals, and flight penalties.
- Reduced open questions to those explicitly listed in the design doc.
- Noted runtime README placeholders in `repo-structure.md`.
- Added health endpoint to backend docs and layout.
- Documented Alembic config path usage in migrations guide.
- Added guidance to use `.env` for configuration and avoid hard-coded env vars.
- Noted ORM model location in data model documentation.
- Documented CI security automation (CodeQL, Gitleaks, Dependabot).
- Added Ruff, Black, and mypy tooling references in CI/CD docs.
- Added quality checks workflow for all branches and PRs to main.
- Scoped CodeQL to Python until frontend code is present.

## 2026-02-04

- Initial creation of instructions folder and documentation set.
