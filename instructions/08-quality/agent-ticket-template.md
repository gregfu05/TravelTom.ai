# Coding-Agent Ticket Template

Use this template when handing work to a coding agent. The goal is not to describe the issue loosely; it is to give the agent enough context, boundaries, and verification detail to execute with minimal guessing.

This template is TravelTom-specific. It encodes the repo's current expectations:

- Start from the relevant instruction docs under `instructions/`.
- Point the agent to the exact runtime paths and tests to inspect first.
- Keep changes small, explicit, and reviewable.
- Update docs whenever behavior, APIs, schemas, or architecture notes change.
- Add or update tests in the same change when business logic changes.

## What makes a strong ticket

- State the outcome, not just the symptom.
- Separate facts from assumptions.
- Name the relevant docs and files up front.
- Specify what is in scope and what is not.
- Define acceptance criteria that can be checked without interpretation.
- Include verification commands when they are known.
- Tell the agent where existing patterns already live in the repo.

## Author checklist

Before handing a ticket to an agent, make sure it:

- Names the subsystem (`backend`, `frontend`, `orchestrator`, `infra`, `docs`, or mixed).
- Links the instruction docs the agent should read first.
- Points to the files or modules most likely to change.
- Describes current behavior and desired behavior separately.
- Calls out constraints, guardrails, and non-goals.
- Lists tests to run or add.
- Lists docs that must be updated.

## Where to point the agent first

Use these as defaults when filling `Repo Context To Read First`.

| Change type | Read first |
| --- | --- |
| Backend API or service | `instructions/02-backend/api-design.md`, `instructions/02-backend/services-and-modules.md`, `instructions/08-quality/code-standards.md`, `instructions/08-quality/testing-strategy.md` |
| DB model or migration | `instructions/02-backend/data-model.md`, `instructions/02-backend/migrations.md`, `instructions/02-backend/services-and-modules.md` |
| Recommender | `instructions/03-recommender/recommender-overview.md`, `instructions/03-recommender/heuristic-ranker-spec.md`, `instructions/03-recommender/explanations.md` |
| Orchestrator, prompts, or tool schemas | `instructions/04-llm-orchestrator/orchestrator-overview.md`, `instructions/04-llm-orchestrator/prompts-and-guardrails.md`, `instructions/04-llm-orchestrator/tool-schemas.md`, `instructions/04-llm-orchestrator/session-state-schema.md` |
| Frontend | `instructions/05-frontend/frontend-architecture.md`, `instructions/05-frontend/ux-flows.md`, `instructions/05-frontend/accessibility-and-i18n.md` |
| Events or analytics | `instructions/06-events-analytics/event-taxonomy.md`, `instructions/06-events-analytics/event-pipeline.md` |
| Infra or ops | `instructions/07-infra-ops/local-dev.md`, `instructions/07-infra-ops/observability.md`, `instructions/07-infra-ops/runbooks.md` |
| Cross-cutting quality or process | `instructions/README.md`, `instructions/08-quality/code-standards.md`, `instructions/08-quality/testing-strategy.md` |

## Canonical template

Copy this block into an issue, task tracker, or direct agent prompt.

```md
# Ticket: <short imperative title>

## Outcome / Goal

<State the end result in one or two sentences. Focus on the user-visible or system-visible outcome.>

## Why / Context

<Explain why this work matters now. Include the problem, the impact, and any relevant history.>

## In Scope

- <Change 1>
- <Change 2>
- <Change 3>

## Out of Scope

- <Explicit non-goal 1>
- <Explicit non-goal 2>

## Repo Context To Read First

- `instructions/<doc-1>.md`
- `instructions/<doc-2>.md`
- `instructions/<doc-3>.md`

## Relevant Files / Modules

- `<path/to/file_or_folder_1>`: <why it matters>
- `<path/to/file_or_folder_2>`: <why it matters>
- `<path/to/test_or_fixture>`: <existing coverage or pattern>

## Current Behavior

<Describe what happens today. Prefer observable facts. If useful, include a failing scenario or error shape.>

## Desired Behavior

<Describe the target behavior in concrete terms. Include the expected API/UI/runtime behavior.>

## Constraints / Non-negotiables

- Follow existing architecture and module boundaries.
- Reuse existing patterns before introducing new abstractions.
- Keep routers thin; put shared backend schemas under `apps/api/app/schemas/`.
- Do not hard-code config or secrets.
- Update docs for any public API, schema, orchestration, ranking, or architecture change.
- Add or update tests in the same change when behavior changes.
- Keep the change small and reviewable.
- <Project- or task-specific constraint>

## Implementation Notes

- Preferred approach: <state the intended shape if already decided>
- Existing pattern to mirror: `<path>`
- Avoid: <known wrong direction, deprecated path, or tempting refactor>
- If assumptions are required, document them explicitly in the final summary.

## Acceptance Criteria

- [ ] <Observable behavior 1>
- [ ] <Observable behavior 2>
- [ ] <Schema/contract/UI expectation>
- [ ] <Doc update expectation>
- [ ] <Test expectation>

## Verification / Tests

- Run: `<command>`
- Run: `<command>`
- Manually verify: <scenario>

## Docs To Update

- `instructions/<doc>.md`
- `instructions/<doc>.md`
- `instructions/CHANGELOG.md` if instruction docs change

## Definition of Done

- Code is implemented.
- Tests relevant to the change pass.
- Docs listed above are updated.
- Final summary includes changed files, verification performed, and any assumptions or follow-ups.

## Open Questions / Assumptions

- Assumption: <default the agent may use if not contradicted by repo context>
- Open question: <only include if truly unresolved and material>
```

## Example

```md
# Ticket: Keep chat router thin and move shared chat contracts into schemas/api

## Outcome / Goal

Refactor the chat API boundary so `apps/api/app/api/v1/chat.py` only handles HTTP wiring, while shared request/response contracts live in `apps/api/app/schemas/api/chat.py`.

## Why / Context

The router currently owns too much request/response shaping and is drifting away from the documented thin-router pattern. This makes reuse harder and increases the chance of inconsistent schema placement.

## In Scope

- Move shared chat request/response models into `schemas/api/chat.py`
- Keep `chat.py` focused on dependency wiring and response mapping
- Update related backend docs
- Update or add tests if imports or behavior change

## Out of Scope

- Changing chat endpoint semantics
- Changing orchestrator decision logic
- Refactoring unrelated routers

## Repo Context To Read First

- `instructions/02-backend/api-design.md`
- `instructions/02-backend/services-and-modules.md`
- `instructions/08-quality/code-standards.md`

## Relevant Files / Modules

- `apps/api/app/api/v1/chat.py`: current router boundary
- `apps/api/app/schemas/api/`: target package for shared HTTP schemas
- `tests/api/test_chat.py`: integration coverage for the endpoint

## Current Behavior

`chat.py` owns API models and request handling details directly, which mixes HTTP contract concerns with router logic.

## Desired Behavior

Shared chat API contracts live under `apps/api/app/schemas/api/chat.py`. The router imports them and stays thin. Endpoint behavior remains unchanged.

## Constraints / Non-negotiables

- Keep shared backend schemas under `apps/api/app/schemas/`
- Do not change the public API contract
- Update backend docs that describe schema/module placement
- Keep the refactor narrow

## Implementation Notes

- Mirror the existing patterns used by other thin routers if present
- Avoid folding unrelated persistence or service refactors into this task

## Acceptance Criteria

- [ ] Shared chat API schemas live under `apps/api/app/schemas/api/chat.py`
- [ ] `apps/api/app/api/v1/chat.py` remains a thin router
- [ ] Existing chat behavior and tests still pass
- [ ] Backend docs are updated to reflect the schema location

## Verification / Tests

- Run: `python -m pytest tests/api/test_chat.py -q`
- Manually review imports to confirm the router no longer defines shared schemas

## Docs To Update

- `instructions/02-backend/api-design.md`
- `instructions/02-backend/services-and-modules.md`

## Definition of Done

- Refactor is merged with tests and docs updated

## Open Questions / Assumptions

- Assumption: only shared API contracts move; module-private helpers can remain local if not reused
```

## Anti-patterns

Avoid tickets that:

- say "fix this" without describing current and desired behavior
- point the agent to no files or too many unrelated files
- ask for a "cleanup" or "refactor" without an acceptance bar
- omit testing expectations
- omit doc updates even though the change touches documented behavior
- mix a narrow fix with broad unrelated redesign work
