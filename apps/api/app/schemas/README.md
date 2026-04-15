# Schema Layer

Purpose: shared runtime contracts for API payloads, tool calls, orchestrator state, and internal service boundaries.

Ownership: Backend.

## What Lives Here

- `api/`: request and response models exposed through HTTP routes.
- `tools/`: tool-call contracts used by recommendation and event flows.
- `state.py`: persisted planner session state.
- `orchestrator.py`: orchestration plans, runtime payloads, and transcript structures.
- `agent.py`, `auth.py`: shared higher-level contracts.

## Design Notes

- This is the canonical home for reusable backend contracts.
- If multiple modules need the same payload shape, place it here rather than in routers or services.
- Keep wire contracts and validation logic aligned with tests under `tests/api/` and `tests/orchestrator/`.

## Related Docs

- `../README.md`
- `../../../../instructions/02-backend/api-design.md`
- `../../../../instructions/04-llm-orchestrator/tool-schemas.md`
- `../../../../instructions/04-llm-orchestrator/session-state-schema.md`
