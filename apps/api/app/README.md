# API App Package

Purpose: internal package for the FastAPI runtime under `apps/api`.

Ownership: Backend.

## What Lives Here

- `api/`: HTTP routers and API version wiring.
- `core/`: config, logging, telemetry, error handling, and security primitives.
- `db/`: SQLAlchemy models, base metadata, and session wiring.
- `repositories/`: persistence boundaries used by services.
- `schemas/`: shared runtime contracts and API/tool payload models.
- `services/`: orchestration, auth flows, recommendation runtime, and other business logic.

## Important Entrypoints

- `main.py`: creates the FastAPI app, configures middleware, telemetry, and startup preload.
- `services/travel_tom_agent.py`: shared LangChain-backed route-facing agent wrapper.
- `services/orchestrator/`: deterministic orchestration and fallback behavior.

## Working Rules

- Keep routers thin and push shared contracts into `schemas/`.
- Prefer service + repository boundaries over route-local business logic.
- If a change affects API behavior, schemas, or orchestration, update the matching docs under `instructions/02-backend/` or `instructions/04-llm-orchestrator/`.

## Related Docs

- `../README.md`
- `../../../instructions/02-backend/services-and-modules.md`
- `../../../instructions/04-llm-orchestrator/orchestrator-overview.md`
