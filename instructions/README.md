# TravelTom Implementation Instructions

This folder is the authoritative implementation guide for the TravelTom project. It translates the design document into concrete architecture, policies, and a step-by-step plan that a coding agent can execute with small, reviewable commits.

If the design document is not available locally, proceed using the assumptions documented in `OPEN_QUESTIONS.md` and treat them as temporary defaults that must be confirmed.

## How to use this folder

1. Read `00-context/design-summary.md` and `00-context/scope-and-milestones.md` first.
2. Review architecture docs in `01-architecture/` to understand boundaries and the repo layout.
3. Use the step-by-step plan in `09-implementation-plan/implementation-plan.md` as the execution checklist.
4. When creating implementation tickets for a coding agent, start from `08-quality/agent-ticket-template.md` so issues are handed off with consistent context, scope, file pointers, and verification criteria.
5. Update documentation as required by each step. Documentation changes are mandatory.
6. Keep `CHANGELOG.md` updated whenever these instructions change.
7. For frontend UI implementation quality, apply `05-frontend/ui-design-skill.md`.

## Rules of engagement for coding agents

- Source of truth: The design document is authoritative. Where it is ambiguous or missing, follow defaults in `OPEN_QUESTIONS.md` and record updates there.
- Determinism first: The Recommendation Service must be deterministic and testable independent of the LLM.
- LLM orchestration only: The LLM must not invent recommendations. It only selects tools, interprets results, and formats responses.
- Strict schema validation: All tool calls and tool responses must use explicit schemas with validation and failure handling.
- Configuration hygiene: Never hard-code environment variables or URLs in code; use `.env` and runtime environment configuration.
- Incremental changes: No sweeping refactors. Each step should be small, with a clear acceptance bar.
- Commit discipline: One logical change per commit. Use the suggested commit message for each step.
- Docs are first-class: Every step requires explicit doc updates.
- Test on change: If a change affects business logic, add or update tests in the same step.
- Zen of Python for backend code: Python changes must follow the enforced standards in `08-quality/code-standards.md` (explicit, simple, readable, fail-fast patterns).

## Quality gates

- Lint, type-check, and unit tests must pass before merging.
- API contracts are versioned and backward compatible within a version.
- Security posture is documented even for MVP (auth, rate limiting, secrets handling).
- Observability is not optional: structured logs and tracing are required for chat and recommendations.
- Python review must pass the Zen of Python checklist in `08-quality/code-standards.md`.

## Doc update policy

- Any new endpoint, schema, or event must update the relevant docs under `02-backend/` and `06-events-analytics/`.
- Any new service or module must update `01-architecture/system-overview.md` and `02-backend/services-and-modules.md`.
- Any ranking logic change must update `03-recommender/heuristic-ranker-spec.md` and `03-recommender/explanations.md`.
- Any LLM prompt or tool change must update `04-llm-orchestrator/` docs.
- Every implementation step must reference the docs it updated.
- Update `CHANGELOG.md` whenever these instructions change.

## Notation

- Relative links are used for internal docs.
- Mermaid diagrams are used for architecture and flows.
- All schemas are defined using Pydantic models or JSON Schema where applicable.
- Shared backend runtime schemas belong under `apps/api/app/schemas/`, not inside `core/`, `services/`, or repository modules.
