# Services and Modules

## Suggested FastAPI layout

```
apps/api/
  app/
    api/
      v1/
        health.py
        chat.py
        recommendations.py
        events.py
        catalog.py
        shortlists.py
        itineraries.py
    core/
      config.py
      logging.py
      telemetry.py
    db/
      base.py
      session.py
      models/
      migrations/
    services/
      orchestrator/
      recommender/
      catalog/
      events/
    schemas/
      api/
      events/
      tools/
      state.py
    main.py
```

## Dependency injection

- Use FastAPI dependency injection for DB sessions, configuration, and service instances.
- Centralize service construction in `app/core/config.py` and `app/services/__init__.py`.

## Module boundaries

- Orchestrator service:
  - Owns LLM interaction and tool orchestration.
  - Cannot construct recommendations directly.
- Recommender service:
  - Owns retrieval and ranking logic.
  - Deterministic outputs with versioned scoring.
- Catalog service:
  - Responsible for catalog CRUD and search.
- Event logger:
  - Validates and writes events with idempotency.

## Settings management

- Use environment-based configuration.
- Validate config with Pydantic Settings.
- Provide a `.env.example` for local dev.
- Do not hard-code environment-specific values (URLs, secrets, endpoints) in code.

## Error handling

- Centralize exception handling in middleware.
- Map internal errors to the API error model.
- Always return `trace_id`.
