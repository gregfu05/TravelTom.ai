# Service Layer

Purpose: business logic for orchestration, recommendation runtime, auth flows, and health/status helpers.

Ownership: Backend.

## What Lives Here

- `travel_tom_agent.py`: route-facing agent integration that bridges LangChain, the orchestrator, and deterministic recommendation execution.
- `orchestrator/`: turn preparation, policy, extraction, decisioning, and response assembly.
- `recommendation_runtime.py` and `recommendation_query.py`: runtime recommendation tool wiring.
- `auth.py`, `local_user_manager.py`: auth/session workflows.
- `chat_uow.py` and `chat_persistence.py`: chat transaction and persistence helpers.
- `health_status.py`: payload construction for the health route.

## Design Notes

- Keep this layer focused on business behavior and orchestration, not HTTP wiring.
- Deterministic recommendation logic should remain testable independently of the LLM path.
- When behavior changes here, update the matching tests and docs in the same change.

## Related Docs

- `../README.md`
- `../../../../instructions/02-backend/services-and-modules.md`
- `../../../../instructions/04-llm-orchestrator/orchestrator-overview.md`
