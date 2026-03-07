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
      chat.py
      users.py
    services/
      auth.py
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
  - Owns LLM planning/composition and tool orchestration.
  - Cannot construct recommendations directly.
  - Validates structured planner/composer outputs and maps them to existing state/tool schemas.
  - Keeps deterministic guardrails for fallback planning, state extraction, and query-filter normalization.
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
  - Owns recommendation-tool execution and tool-response validation.
  - Converts API request/response schemas to/from tool-layer schemas.
  - Keeps the recommendations router focused on DI and HTTP error mapping.
- Chat repository (`app/repositories/chat.py`):
  - Owns chat persistence operations: session lookup/creation, message writes,
    and recommendation snapshot writes.
  - Provides feature-specific data access (non-generic repository pattern).
- User repository (`app/repositories/users.py`):
  - Resolves authenticated principals to internal `users` rows.
  - Owns external OIDC subject lookup, local-email lookup, and minimal user upsert behavior.
- Auth service (`app/services/auth.py`):
  - Owns local email/password signup, login, and current-user resolution.
  - Issues TravelTom local bearer tokens from configured runtime secrets.
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
  - Own bearer-token verification, Azure AD B2C integration, and chat rate limiting.
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
