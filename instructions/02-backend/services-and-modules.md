# Services and Modules

## Suggested FastAPI layout

```
apps/api/
  app/
    api/
      v1/
        auth.py
        health.py
        chat.py
        recommendations.py
        events.py
        catalog.py
        shortlists.py
        itineraries.py
    core/
      config.py
      errors.py
      security.py
      logging.py
      telemetry.py
    db/
      base.py
      session.py
      models/
      migrations/
    repositories/
      auth_sessions.py
      chat.py
      users.py
    services/
      auth.py
      local_user_manager.py
      travel_tom_agent.py
      orchestrator/
      recommender/
      catalog/
      events/
      health_status.py
      recommendation_query.py
      chat_uow.py
      chat_persistence.py
    schemas/
      auth.py
      orchestrator.py
      api/
        auth.py
        chat.py
        health.py
        recommendations.py
      events/
      tools/
      state.py
    main.py
```

## Dependency injection

- Use FastAPI dependency injection for DB sessions, configuration, and service instances.
- Centralize service construction in `app/core/config.py` and `app/services/__init__.py`.
- Keep auth and rate-limit dependencies in `app/core/security.py`.

## Module boundaries

- Orchestrator service:
  - Owns planner/composer orchestration, deterministic fallback logic, and
    grounded response normalization.
  - Does not own route wiring or LangChain tool registration.
  - Keeps deterministic guardrails for fallback planning, state extraction,
    structured state-patch merging, and query-filter normalization.
  - Converts validated recommendation data into route-safe `OrchestratorResponse`
    payloads.
- TravelTom agent service (`app/services/travel_tom_agent.py`):
  - Owns the route-facing backend agent abstraction used by `/chat` and `/recommendations/query`.
  - Owns planner/composer model invocation for `/chat` and LangChain-native
    `create_agent` construction for `direct_recommendation` mode.
  - Owns `@tool` registration for the shared deterministic recommendation tool.
  - Delegates chat turn orchestration and fallback logic to `OrchestratorService`.
  - Wraps deterministic recommendation execution without changing recommender logic.
- Orchestrator model provider (`app/services/orchestrator/llm_provider.py`):
  - Owns chat-model construction for OpenAI and Ollama planner/composer calls.
  - Owns deterministic in-process models for disabled chat fallback and direct
    recommendation mode.
- Recommender service:
  - Owns retrieval and ranking logic.
  - Deterministic outputs with versioned scoring.
- Catalog service:
  - Responsible for catalog CRUD and search.
- Event logger:
  - Validates and writes events with idempotency.
- Health status service (`app/services/health_status.py`):
  - Owns health payload construction for `/health`.
  - Keeps router logic limited to HTTP wiring.
- Recommendation query service (`app/services/recommendation_query.py`):
  - Owns shared recommendation execution error types and request/response
    normalization helpers used by agent-backed deterministic flows.
  - Keeps recommendation error normalization separate from route HTTP mapping.
- Chat repository (`app/repositories/chat.py`):
  - Owns chat persistence operations: session lookup/creation, bounded recent
    message reads, message writes, and recommendation snapshot writes.
  - Provides feature-specific data access (non-generic repository pattern).
- User repository (`app/repositories/users.py`):
  - Resolves authenticated principals to internal `users` rows.
  - Owns external OIDC subject lookup, local-email lookup, and minimal user upsert behavior.
- Auth-session repository (`app/repositories/auth_sessions.py`):
  - Persists local bearer-token sessions used for logout and timeout enforcement.
  - Owns lookup, idle-timeout extension, and revocation of local auth sessions.
- Auth service (`app/services/auth.py`):
  - Owns local email/password signup, login, logout, and current-user resolution.
  - Uses an app-owned `fastapi-users` adapter for local user creation and password verification.
  - Issues TravelTom local bearer tokens from configured runtime secrets.
  - Creates persisted local auth sessions before token issuance.
- Local user manager (`app/services/local_user_manager.py`):
  - Adapts `fastapi-users` to the existing `users` table without adopting library routers.
  - Keeps library-specific user/password logic behind app-owned services.
- Chat unit of work (`app/services/chat_uow.py`):
  - Owns chat transaction lifecycle (`flush`/`commit`/`rollback`).
  - Wires the chat and user repositories to a request-scoped DB session.
- Chat persistence helpers (`app/services/chat_persistence.py`):
  - Owns deterministic session-id-to-UUID mapping via `uuid5`.
  - Validates and hydrates persisted state payloads for orchestrator execution.
  - Sanitizes deprecated client-controlled `user_id` values from state hydration.
- Error helpers (`app/core/errors.py`):
  - Own structured error responses and per-request trace IDs.
- Security helpers (`app/core/security.py`):
  - Own local bearer-token verification, auth-session timeout checks, logout-aware
    token rejection, Azure bearer fallback, and chat rate limiting.
- Shared schema modules (`app/schemas/*.py`):
  - Own cross-module Pydantic contracts used by multiple runtime layers.
  - Keep auth principals, token claims, state payloads, and orchestrator contracts out of `core/` and `services/` modules.

## Settings management

- Use environment-based configuration.
- Validate config with Pydantic Settings.
- Provide a `.env.example` for local dev.
- Do not hard-code environment-specific values (URLs, secrets, endpoints) in code.

## Error handling

- Centralize exception handling in middleware.
- Map internal errors to the API error model.
- Always return `trace_id`.
