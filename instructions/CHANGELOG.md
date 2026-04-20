# Instructions Changelog

## Unreleased

- Updated orchestrator and frontend guidance so hotel searches become
  search-ready with destination and dates, while budget is treated as an
  optional refinement input.
- Documented clarification-copy guardrails that reject model-written prompts
  when they drift away from the backend-computed missing slot.
- Refreshed chat runtime docs and verification guidance after state-integrity
  fixes:
  - `04-llm-orchestrator/session-state-schema.md` now documents budget-optional
    hotel slot gating and carried-query preservation for vague empty-result
    follow-ups.
  - `04-llm-orchestrator/prompts-and-guardrails.md` now documents
    search-type-before-budget clarification, unsupported-flight state fencing,
    and the inline-budget one-shot contract.
  - `07-infra-ops/local-dev.md`, `08-quality/testing-strategy.md`, and
    `scripts/README.md` now reflect the current provider defaults,
    Docker-to-host Ollama note, auth-aware smoke usage, and the expanded chat
    smoke matrix.
- Added a repo-native chat audit matrix and aligned verification coverage
  around it:
  - `docs/chat-feature-audit.md` maps the required chat scenarios to expected
    slot/state outcomes, current automated evidence, and remaining manual
    release checks.
  - `scripts/smoke-chat-runtime.ps1` now exercises same-session refinement
    continuity and vague follow-up handling after empty results.
  - `apps/web/e2e/planner-smoke.spec.ts` now includes a retry/recovery flow in
    addition to the planner happy path.
- Tightened orchestrator-side response composition without making fallback copy
  feel rigid:
  - `04-llm-orchestrator/prompts-and-guardrails.md` and
    `04-llm-orchestrator/orchestrator-overview.md` now document stricter
    grounded result-summary validation plus curated deterministic response
    variants.
  - `08-quality/testing-strategy.md` now calls out semantic assertions for
    intentional copy variation and result-composer grounding checks.

## 2026-04-17

- Hardened the dev Azure deployment path and aligned runtime docs with the
  active recommender implementation:
  - `Deploy Dev` now documents and expects migrations before rollout, catalog
    seeding when the target dev database is empty, and auth-aware chat smoke in
    addition to API and web smoke coverage.
  - `07-infra-ops/deployment-final.md`, `07-infra-ops/runbooks.md`, and
    `08-quality/ci-cd.md` now describe the stronger dev rollout path and the
    required target-database secret input.
  - `03-recommender/recommender-overview.md` and
    `02-backend/services-and-modules.md` now align the documented live API
    recommendation path with `recommendor_v3`.

## 2026-04-16

- Re-aligned seed and local-dev docs with the current dataset contract:
  - `scripts/seed_catalog.py` now treats
    `traveltom/datasets/composite/traveltom_clean.csv` as the canonical seed
    input and no longer documents or depends on Parquet-era fallback behavior.
  - `README.md`, `scripts/README.md`, `03-recommender/recommender-overview.md`,
    `07-infra-ops/local-dev.md`, and `traveltom/datasets/README.md` now
    describe the canonical CSV seed path and mark legacy Parquet artifacts as
    offline-only.
- Refreshed the runtime docs after planner/composer diagnostics and Ollama
  reliability fixes:
  - `README.md` now merges the current backend-owned orchestration model with a
    more visual overview, including architecture and chat-flow diagrams.
  - `apps/api/README.md`, `02-backend/api-design.md`, and
    `02-backend/services-and-modules.md` now reflect the shared PostgreSQL-backed
    recommendation runtime, local/dev diagnostics headers, and the native Ollama
    structured endpoint preference.
  - `04-llm-orchestrator/orchestrator-overview.md`,
    `07-infra-ops/local-dev.md`, `07-infra-ops/observability.md`,
    `08-quality/testing-strategy.md`, and `docs/ollama-remote-deployment.md`
    now document auth-aware smoke checks, degraded-mode visibility,
    attempted-versus-used planner/composer signals, and the higher effective
    local Ollama stage budgets.

## 2026-04-15

- Re-documented the chat runtime after the deterministic-core repair:
  - `README.md` now describes `/api/v1/chat` as backend-owned orchestration with
    optional planner/composer helpers instead of a free-form chat-agent loop.
  - `04-llm-orchestrator/orchestrator-overview.md`,
    `04-llm-orchestrator/prompts-and-guardrails.md`, and
    `04-llm-orchestrator/tool-schemas.md` now reflect the planner/composer-only
    provider role and backend-owned recommendation execution.
  - `03-recommender/recommender-overview.md` now records `catalog_items` as the
    live API runtime source of truth.
  - `07-infra-ops/local-dev.md`, `07-infra-ops/observability.md`, and
    `08-quality/testing-strategy.md` now document planner/composer stage budgets,
    provider degradation signals, and the new chat smoke workflow.
  - `docs/ollama-remote-deployment.md` now documents remote Ollama rollout for
    the planner/composer-only integration model.
- Added `scripts/smoke-chat-runtime.ps1` for greeting, slot-gating, follow-up,
  repair-turn, and direct recommendation runtime verification.

## 2026-04-14

- Hardened Azure deployment modules and workflows with shared resource tags,
  Container App probe/resource controls, secret-based DB runtime wiring, deploy
  concurrency, revision capture, stronger smoke checks, and promotion validation.
- Documented the phased orchestrator refactor while preserving runtime behavior:
  - `04-llm-orchestrator/orchestrator-overview.md` now describes the internal
    `TurnPreparer`, `RecommendationDecisionEngine`,
    `RecommendationRunner`, `ResponseAssembler`, and typed runtime-contract
    layers that sit under `OrchestratorService`.
  - `04-llm-orchestrator/prompts-and-guardrails.md` now records the phased
    runtime boundary and the internal typed agent-result normalization step
    used before transcript inspection.
  - `02-backend/services-and-modules.md` now documents `TravelTomAgent` as a
    runtime adapter and records the narrower responsibilities of the new
    orchestrator collaborators.

## 2026-04-10

- Documented the Azure runtime deployment implementation surface:
  - `07-infra-ops/deployment-final.md` now references the repo-managed
    Bicep modules under `infra/azure/`, the runtime env var contract, the
    smoke scripts, and the GitHub Actions deployment workflow names.
  - `07-infra-ops/observability.md` now documents Azure Monitor/App Insights
    export, frontend request trace propagation, and the dashboard seed file.
  - `07-infra-ops/runbooks.md` now references the deploy/rollback workflows
    and the exact smoke-check commands used during rollout and recovery.
  - `08-quality/ci-cd.md` now documents the image-publish, dev deploy, prod
    deploy, and rollback workflow split plus OIDC-based Azure auth.
  - `02-backend/security.md` now states that production telemetry uses
    `APPLICATIONINSIGHTS_CONNECTION_STRING`.

## 2026-04-08

- Refactored the frontend into folderized page/component units and a planner
  feature slice:
  - `apps/web/src/pages/*` and `apps/web/src/components/*` now use per-unit
    folders with colocated tests.
  - Planner-specific chat UI and non-UI helpers now live under
    `apps/web/src/features/planner/` instead of the shared `components/`
    folder.
  - `apps/web/src/app/routes.tsx` now owns route registration so `App.tsx`
    stays focused on shell + router composition.
  - Frontend styles now load from `apps/web/src/styles/index.css` and are split
    across `tokens.css`, `base.css`, `marketing.css`, `auth.css`,
    `planner.css`, and `responsive.css`, removing duplicated planner/drawer CSS.
  - Updated `05-frontend/frontend-architecture.md` and
    `05-frontend/ux-flows.md` to document the new structure and planner mobile
    recommendations path.

- Documented the frontend test-suite overhaul:
  - `05-frontend/frontend-architecture.md` now records the `Vitest` + React Testing Library + Playwright stack.
  - `08-quality/testing-strategy.md` now includes the concrete frontend test commands for unit/DOM, E2E smoke, combined CI, and build verification.

- Updated frontend docs to document branded `/login` and `/signup` routes,
  shared navigation back to the landing page, and preserved redirect behavior
  across auth entry screens.
- Documented the frontend UI/UX cleanup pass:
  - shared navigation now requires a mobile-accessible fallback path
  - homepage/product copy now reflects the current shipped planner state
  - frontend guidance no longer describes active UI surfaces as future work

## 2026-03-24

- Shifted `/api/v1/chat` orchestration back to planner-first extraction and
  conversation control without changing recommender behavior:
  - `apps/api/app/services/orchestrator/service.py` now invokes the planner for
    normal non-empty chat turns instead of skipping greetings, slot-filling
    replies, search-type replies, and common follow-up refinements, while
    keeping deterministic recommendation execution as a failure fallback.
  - `apps/api/app/services/orchestrator/extraction.py` now hardens
    deterministic fallback so filler phrases like `be honest` and `lower cost`
    cannot overwrite a valid destination, and lower-cost follow-ups preserve
    hotel/restaurant/activity continuity.
  - `apps/api/app/services/orchestrator/policies.py` and
    `apps/api/app/services/travel_tom_agent.py` now document and enforce that
    the planner owns natural-language slot extraction on normal chat turns,
    while grounded recommendation content still comes only from validated tool
    output.
  - `tests/orchestrator/test_service.py`,
    `tests/orchestrator/test_extraction.py`,
    `04-llm-orchestrator/orchestrator-overview.md`,
    `04-llm-orchestrator/prompts-and-guardrails.md`, and
    `04-llm-orchestrator/session-state-schema.md` now cover and describe the
    planner-first hybrid flow and fallback destination-safety guardrails.

## 2026-03-23

- Documented the implemented chat coherence fixes:
  - `04-llm-orchestrator/orchestrator-overview.md` now documents planner bypass
    for deterministic turns, search-type clarification, item-type-aware slot
    requirements, and stronger empty-results guidance.
  - `04-llm-orchestrator/prompts-and-guardrails.md` now documents the
    `search_type` / `refine_preference` clarification branches, generic
    trip-to-recommendation promotion, unsupported-flight handling, and
    mixed one-shot destination/date/budget parsing.
  - `04-llm-orchestrator/session-state-schema.md` now includes
    `conversation.last_clarification_kind` and
    `conversation.last_search_outcome`, plus the item-type-aware required-slot
    rules.
  - `05-frontend/ux-flows.md` now documents backend-backed planner hydration
    and the current chat progression from greeting through search-type
    clarification and grounded/no-results outcomes.

## 2026-03-19

- Fixed four high-impact `/api/v1/chat` regressions in the orchestrator layer
  without changing dataset or recommender behavior:
  - `apps/api/app/services/orchestrator/providers/ollama.py` now prefers
    Ollama's OpenAI-compatible structured endpoint with JSON-schema constrained
    planner output and a higher structured timeout floor, so planner transport
    failures are no longer caused by the old silent timeout path.
  - `apps/api/app/services/orchestrator/extraction.py` now uses token-aware and
    negation-aware interest matching so `Santa Barbara` does not imply `bar`
    and repair turns like `not restaurants` do not add positive restaurant
    interest.
  - `apps/api/app/services/orchestrator/policies.py` and
    `apps/api/app/services/orchestrator/service.py` now keep meta questions and
    repair turns conversational, truncate long transcript replay for planning,
    and suppress duplicate-only `show me more` follow-ups by tracking the last
    surfaced grounded item ids in `SessionState.conversation`.
  - `apps/api/app/schemas/state.py`, `tests/orchestrator/test_service.py`,
    `tests/orchestrator/test_extraction.py`, `tests/orchestrator/test_llm_provider.py`,
    and `tests/api/test_chat.py` now cover planner transport behavior, Santa
    Barbara tokenization, repair-turn interest handling, transcript truncation,
    and duplicate follow-up suppression.
  - `04-llm-orchestrator/orchestrator-overview.md`,
    `04-llm-orchestrator/prompts-and-guardrails.md`,
    `04-llm-orchestrator/session-state-schema.md`, and
    `02-backend/services-and-modules.md` now document the updated runtime.

- Introduced schema-validated planner-first `/api/v1/chat` orchestration while
  keeping deterministic recommendation grounding:
  - `apps/api/app/services/orchestrator/service.py` now runs a structured
    planner step after deterministic hint extraction, validates
    `LLMOrchestrationPlan`, merges `state_patch` through
    `apply_structured_state_patch(...)`, threads validated `query_controls`
    into hidden recommendation context, and falls back to deterministic
    behavior when planner output is missing or invalid.
  - `apps/api/app/services/travel_tom_agent.py` now builds a provider-backed
    structured planner client for `/chat` while keeping the LangChain
    `create_agent` loop and deterministic direct recommendation mode intact.
  - `apps/api/app/services/orchestrator/policies.py` now feeds the planner raw
    user text, bounded recent transcript, validated current state, and
    deterministic extraction/carry-forward hints.
  - `tests/orchestrator/test_service.py` now covers planner prompt context,
    planner-authored natural slot filling, planner query-control shaping, and
    deterministic fallback when planner state patches fail validation.
  - `04-llm-orchestrator/orchestrator-overview.md`,
    `04-llm-orchestrator/prompts-and-guardrails.md`,
    `04-llm-orchestrator/session-state-schema.md`, and
    `02-backend/services-and-modules.md` now describe the hybrid
    planner-plus-deterministic runtime.

- Tightened destination extraction guardrails so greetings and meta replies no
  longer seed fake trip state:
  - `apps/api/app/services/orchestrator/extraction.py` now only accepts
    assignment-style `destination ...` phrases, rejects conversational bare
    phrases like `Hello Tommy`, and avoids treating meta uses of the word
    `destination` as active destination-exploration intent.
  - `tests/orchestrator/test_extraction.py` and
    `tests/orchestrator/test_service.py` now cover the exact greeting/meta
    repro and verify that those turns keep destination state empty while real
    bare replies like `Lisbon` still work.
  - `04-llm-orchestrator/orchestrator-overview.md`,
    `04-llm-orchestrator/prompts-and-guardrails.md`, and
    `04-llm-orchestrator/session-state-schema.md` now document the stricter
    destination-capture behavior.

# 2026-04-14

- Added dev-first Azure MLOps foundation in `infra/azure/` with optional Azure
  ML workspace, blob-backed artifact storage, and managed identity wiring.
- Added dev ML GitHub workflows for training, offline evaluation, and
  promotion into the API runtime.
- Updated the ML ranker runtime to resolve promoted artifacts from environment
  configuration, including private Azure Blob URLs with managed-identity access.
- Added training-manifest and offline-gate helper scripts for reproducible ML
  artifact publication and promotion checks.
- Updated infra, CI/CD, runbook, and MLOps planning docs to make prod rollout
  explicitly contingent on dev-path stability.

## 2026-03-18

- Fixed chat recommendation deadlocks and restored grounded reply composition:
  - `apps/api/app/services/orchestrator/service.py` now preserves pending
    recommendation query/item-type memory during clarification, re-asks the same
    missing slot until captured, and runs the deterministic recommendation path
    immediately when the final required detail arrives but the agent still
    clarifies.
  - `apps/api/app/services/orchestrator/extraction.py` now rejects vague bare
    phrases such as `Beach + relax`, `recommend a beach trip`, `show me more`,
    and `cheaper` as destinations while still carrying recommendation intent
    through slot-filling turns.
  - `apps/api/app/services/orchestrator/policies.py` now implements the hybrid
    recommendation policy: destination exploration can start from partial signal,
    while hotel searches still require destination, dates, and budget, and
    restaurant/activity searches require destination.
  - `apps/api/app/services/travel_tom_agent.py` now adds provider-backed
    grounded response composition after validated tool/state normalization so
    Ollama/OpenAI replies stay natural without allowing model-invented items.
  - `apps/api/app/core/config.py`, `.env`, and `.env.example` now default local
    chat to `ORCHESTRATOR_LLM_PROVIDER=ollama`; `disabled` remains the fallback
    and test mode.
  - `apps/web/src/components/ChatView.tsx` now uses planner chips and helper
    copy that match backend recommendation timing.
- Updated regression coverage and docs for the new behavior:
  - `tests/orchestrator/test_service.py`
  - `tests/orchestrator/test_extraction.py`
  - `tests/api/test_chat.py`
  - `tests/test_settings.py`
  - `04-llm-orchestrator/orchestrator-overview.md`
  - `04-llm-orchestrator/prompts-and-guardrails.md`
  - `04-llm-orchestrator/session-state-schema.md`
  - `02-backend/api-design.md`
  - `02-backend/services-and-modules.md`
  - `05-frontend/frontend-architecture.md`
  - `05-frontend/ux-flows.md`
  - `07-infra-ops/local-dev.md`

- Restored `/api/v1/chat` to a true LangChain `create_agent` loop while keeping
  deterministic recommendation shaping:
  - `apps/api/app/services/travel_tom_agent.py` now rebuilds the shared chat
    agent instead of routing normal chat through planner/composer model calls.
  - `apps/api/app/services/orchestrator/service.py` now prepares hidden runtime
    state + carry-forward context for the agent, normalizes agent transcripts,
    and preserves deterministic fallback recommendation execution.
  - `apps/api/app/services/orchestrator/extraction.py` now resolves effective
    carried item type and effective recommender query text for elliptical
    follow-up turns.
  - `apps/api/app/schemas/state.py` now remembers the last effective
    recommendation item type and query text in `conversation`.
  - `apps/api/app/services/orchestrator/llm_provider.py` deterministic disabled
    mode now consumes the same hidden carry-forward context as the real agent path.
- Updated orchestrator/backend docs to reflect the restored chat-agent runtime:
  - `04-llm-orchestrator/orchestrator-overview.md`
  - `04-llm-orchestrator/prompts-and-guardrails.md`
  - `04-llm-orchestrator/session-state-schema.md`
  - `02-backend/api-design.md`
  - `02-backend/services-and-modules.md`
- Updated tests for the restored behavior:
  - `tests/orchestrator/test_extraction.py`
  - `tests/orchestrator/test_service.py`

## 2026-03-16

- Redesigned chat orchestration to use bounded recent transcript replay plus
  conversation-aware state:
  - `apps/api/app/services/orchestrator/service.py` now runs
    deterministic extraction, structured planning, optional deterministic
    recommendation execution, and grounded response composition per turn.
  - `apps/api/app/services/travel_tom_agent.py` now invokes planner/composer
    model calls for `/api/v1/chat` while keeping direct recommendation mode
    LangChain-agent backed.
  - `apps/api/app/repositories/chat.py` now exposes bounded recent-message reads
    for orchestration input.
  - `apps/api/app/schemas/state.py` now includes `conversation.last_requested_slots`
    and `conversation.last_user_intent`.
  - Updated orchestrator/chat tests for multi-turn carryover, progressive
    clarification, refine continuity, and route-level transcript threading.
- Updated backend/orchestrator docs for the implemented chat runtime:
  - `04-llm-orchestrator/orchestrator-overview.md`
  - `04-llm-orchestrator/prompts-and-guardrails.md`
  - `04-llm-orchestrator/session-state-schema.md`
  - `02-backend/services-and-modules.md`

- Documented centralized frontend JSON request serialization:
  - `05-frontend/frontend-architecture.md` now states that JSON request bodies
    must be serialized in one shared `apiClient` helper and that call sites
    should pass plain objects.

- Documented chat 429 classification and recovery behavior:
  - `02-backend/api-design.md` now distinguishes TravelTom-owned throttling
    from upstream provider rate limits and documents `Retry-After`.
  - `02-backend/security.md` now documents explicit local/dev rate-limit policy
    and required limiter diagnostics.
  - `05-frontend/frontend-architecture.md` now documents cooldown-aware chat UX
    and provider-specific 429 handling.
  - `07-infra-ops/local-dev.md`, `07-infra-ops/observability.md`, and
    `07-infra-ops/runbooks.md` now include chat 429 troubleshooting and
    classification steps.

## 2026-03-15

- Updated backend auth docs to reflect the local-auth library migration:
  - `02-backend/api-design.md` now documents the app-owned `fastapi-users` adapter
    behind the existing `/api/v1/auth/*` contract.
  - `02-backend/services-and-modules.md` now includes `local_user_manager.py`
    and clarifies that library-specific local-user logic stays behind app services.
  - `02-backend/security.md` now distinguishes library-backed local credentials
    from app-owned `auth_sessions` enforcement and PyJWT-issued bearer tokens.
  - `02-backend/data-model.md` now notes that `users.password_hash` is managed by
    the local-auth library integration.
  - `02-backend/migrations.md` now states that the migration reuses the existing
    `users.password_hash` and `auth_sessions` schema unless the table shape changes.
  - `07-infra-ops/local-dev.md` now documents the local-dev dependency/runtime
    expectations for library-backed local auth.

## 2026-03-12

- Reworked the backend agent runtime around LangChain-native `create_agent` and
  `@tool`:
  - `apps/api/app/services/travel_tom_agent.py` now builds two real LangChain
    agents:
    - a bounded chat agent for `/api/v1/chat`
    - a deterministic direct recommendation agent for
      `/api/v1/recommendations/query`
  - Replaced the old compatibility-layer runtime path with LangChain-native tool
    registration and transcript normalization.
  - `apps/api/app/services/orchestrator/llm_provider.py` now builds
    `ChatOpenAI` / `ChatOllama` models and deterministic in-process models for
    disabled/direct modes.
  - `apps/api/app/services/orchestrator/service.py` now normalizes agent
    transcripts and keeps deterministic fallback behavior for model failure,
    invalid tool calls, tool timeout, invalid tool payload, tool failure, and
    empty results.
  - Added `RecommendationToolRuntimePayload` to
    `apps/api/app/schemas/orchestrator.py` for schema-valid tool artifacts.
  - Updated orchestrator/provider tests for the new LangChain-native contract.
- Added runtime dependencies for the new backend path:
  - `langchain`
  - `langchain-openai`
  - `langchain-ollama`
- Refactored backend route wiring to use a shared `TravelTomAgent` entrypoint:
  - Added `apps/api/app/services/travel_tom_agent.py` and
    `apps/api/app/schemas/agent.py`.
  - `/api/v1/chat` now resolves `TravelTomAgent.handle_chat(...)` instead of
    injecting `OrchestratorService` directly.
  - `/api/v1/recommendations/query` now resolves
    `TravelTomAgent.handle_recommendation_query(...)` instead of injecting the raw
    recommendation tool.
  - Moved LangChain-compatible recommendation tool registration/invocation to the
    shared agent layer while keeping recommender behavior deterministic.
  - Updated backend/orchestrator docs and route tests for the new dependency
    boundary.
- Updated orchestrator docs to reflect the broader response-composition path:
  - `04-llm-orchestrator/orchestrator-overview.md` now documents composed
    clarification and invalid-request replies alongside results and empty-results.
  - `04-llm-orchestrator/prompts-and-guardrails.md` now defines the TravelTom
    warm-expert persona, composed outcome types, and the deterministic failure
    paths that still bypass the composer.

## 2026-03-09

- Added compose-based local DB bootstrap under `infra/docker/`:
  - `docker-compose.yml` now defines local `postgres` + one-shot `migrate`.
  - `docker-compose.seed.yml` adds a one-shot `seed` overlay.
  - `Dockerfile` provides the shared Python utility image used by both jobs.
  - Local Postgres bootstrap now enables `pgvector` with an init SQL script.
- Updated `07-infra-ops/local-dev.md` and `infra/docker/README.md` with exact
  compose workflows for DB + migrations and DB + migrations + seed.

## 2026-03-07

- Added `08-quality/agent-ticket-template.md` as the canonical ticket/prompt format for handing work to coding agents.
- Updated `README.md` to direct instruction authors to the new ticket template when creating implementation tickets.
- Codified schema-placement rules in the quality instructions:
  - Shared backend Pydantic contracts must live under `apps/api/app/schemas/`.
  - Added explicit guidance to keep cross-module schema models out of `core/`,
    `services/`, repositories, and router modules.
- Updated backend architecture/docs to reflect the implemented local-auth path:
  - Added auth endpoint documentation to `02-backend/api-design.md`.
  - Updated `02-backend/security.md` and `07-infra-ops/local-dev.md` with
    `LOCAL_AUTH_TOKEN_SECRET`, token TTL, and local signup/login behavior.
  - Updated `02-backend/services-and-modules.md` and
    `01-architecture/system-overview.md` to document shared schema placement and
    local auth service/runtime boundaries.
- Documented the implemented backend auth path with `AUTH_ENABLED`, Azure AD B2C bearer auth, and chat session ownership enforcement.
- Updated backend API and module docs for structured error responses, `repositories/users.py`, and deprecated request-body `user_id`.
- Extended the data model docs with external OIDC identity fields on `users`.
- Updated the architecture overview to include backend auth and rate limiting in the request path.
- Added local auth-session persistence and lifecycle controls:
  - Added `auth_sessions` persistence model and Alembic migration.
  - Local bearer tokens now carry a persisted `jti` and are checked against
    absolute expiry, idle timeout, and logout revocation state.
  - Added `POST /api/v1/auth/logout`.
  - Added `LOCAL_AUTH_TOKEN_IDLE_TIMEOUT_SECONDS` configuration and `.env.example` entry.
- Updated backend docs to state that the current end-to-end auth/session lifecycle
  is local-only and Azure AD B2C deployment/provider work is deferred.

## 2026-02-26

- Added local Ollama provider wiring for orchestrator structured LLM calls:
  - New provider module:
    `apps/api/app/services/orchestrator/llm_provider.py`
  - Chat DI now builds planner/composer callables from settings in
    `apps/api/app/api/v1/chat.py`
  - Added provider configuration in `apps/api/app/core/config.py`
  - Added new `.env.example` keys:
    `ORCHESTRATOR_LLM_PROVIDER`, `ORCHESTRATOR_LLM_TIMEOUT_SECONDS`,
    `OLLAMA_BASE_URL`, `OLLAMA_PLANNING_MODEL`, `OLLAMA_RESPONSE_MODEL`,
    `OLLAMA_TEMPERATURE`
  - Added provider unit tests:
    `tests/orchestrator/test_llm_provider.py`
  - Updated local dev instructions for Ollama setup in
    `instructions/07-infra-ops/local-dev.md`
- Renamed orchestrator provider fallback mode from `heuristic` to `disabled`
  to avoid confusion with recommender ranking version names.
- Refactored orchestrator provider implementation for cleaner module boundaries:
  - Moved `OllamaStructuredClient` out of the provider factory file into
    `apps/api/app/services/orchestrator/providers/ollama.py`
  - Added shared provider helpers in
    `apps/api/app/services/orchestrator/providers/common.py`
  - Added OpenAI structured client in
    `apps/api/app/services/orchestrator/providers/openai.py`
  - Updated provider factory (`llm_provider.py`) to only handle provider
    selection and binding.
  - Added OpenAI provider config keys and `.env.example` entries:
    `ORCHESTRATOR_OPENAI_BASE_URL`, `ORCHESTRATOR_OPENAI_API_KEY`,
    `OPENAI_PLANNING_MODEL`, `OPENAI_RESPONSE_MODEL`, `OPENAI_TEMPERATURE`
  - Added provider tests for OpenAI path and required API-key validation.

- Refactored orchestrator runtime to an LLM-first flow in
  `apps/api/app/services/orchestrator/service.py`:
  - Added structured planner and response-composer model boundaries.
  - Planner now drives intent interpretation, clarification strategy, and
    query-control shaping.
  - Recommendation execution remains deterministic and tool-backed with
    unchanged ranking behavior (`heuristic-v1`).
  - Added explicit fallback handling for planner failure/invalid output,
    tool timeout, invalid tool payload, empty tool results, and response-model
    failure/invalid output.
- Added structured LLM orchestration contracts and prompt-context builders in
  `apps/api/app/services/orchestrator/policies.py`.
- Added `apply_structured_state_patch` in
  `apps/api/app/services/orchestrator/extraction.py` for validated LLM state
  patch merging, while keeping deterministic extraction as guardrails.
- Extended `apps/api/app/services/orchestrator/langchain_compat.py` with
  `normalize_structured_payload` for consistent structured model output handling.
- Updated orchestrator tests to mock planner/composer/tool boundaries and verify
  deterministic fallbacks and error-path behavior:
  - `tests/orchestrator/test_service.py`
  - `tests/orchestrator/test_extraction.py`
- Updated orchestrator and backend docs for LLM-first behavior and unchanged API
  contract:
  - `04-llm-orchestrator/orchestrator-overview.md`
  - `04-llm-orchestrator/prompts-and-guardrails.md`
  - `04-llm-orchestrator/tool-schemas.md`
  - `04-llm-orchestrator/session-state-schema.md`
  - `02-backend/api-design.md`
  - `02-backend/services-and-modules.md`

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
  hard item-type filtering in recommender (`hotel|restaurant|activity`).
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
- Refined recommender specs with retrieval sizes and ranking signals for the
  supported recommendation types.
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
