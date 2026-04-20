# Ticket: Align chat contracts, docs, smoke expectations, and release matrix

## Outcome / Goal

Create one consistent product contract for chat so runtime rules, tests, smoke
scripts, and instruction docs all agree on supported behavior before behavior
fixes land.

## Why / Context

The repo currently contains drift around core chat behavior:

- `orchestrator-overview.md` says hotel budget is optional
- `session-state-schema.md` still says hotel requires budget
- smoke and test expectations no longer fully match runtime policy
- `docs/README.md` referenced a chat artifact that did not exist

This drift makes defects harder to triage because failures can come from stale
expectations rather than actual runtime regressions.

## In Scope

- Align chat documentation around budget-optional hotel search
- Define the canonical supported scenario matrix for provider-assisted and
  deterministic fallback chat
- Update smoke assertions and failing tests to reflect the intended contract
- Add the repo-native chat ticket set and fix the docs index

## Out of Scope

- Runtime behavior fixes to extraction, provider connectivity, or timeout logic
- Broad documentation cleanup outside chat-related material

## Repo Context To Read First

- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/08-quality/testing-strategy.md`

## Relevant Files / Modules

- `instructions/04-llm-orchestrator/*.md`: chat contract docs
- `instructions/07-infra-ops/local-dev.md`: local verification behavior and
  diagnostic expectations
- `instructions/08-quality/testing-strategy.md`: chat verification guidance
- `scripts/smoke-chat-runtime.ps1`: live smoke expectations
- `tests/orchestrator/test_eval_conversations.py`: scenario-level chat contract
- `tests/orchestrator/test_service.py`: slot gating and clarification behavior
- `docs/README.md`: docs index and chat artifact reference

## Current Behavior

There is no single authoritative description of:

- required slots by item type
- whether hotel budget is required
- when search-type clarification should happen
- what provider-assisted success/failure looks like in local/dev verification

## Desired Behavior

There is one explicit contract for:

- required slots by item type
- unsupported intent handling
- clarification ordering
- follow-up carry-forward behavior
- provider-assisted versus fallback acceptance expectations

That contract is reflected consistently across docs, tests, and smoke tooling.

## Constraints / Non-negotiables

- Do not document behavior that runtime is not intended to support.
- Keep the release matrix concrete and executable.
- Preserve budget-optional hotel policy.
- Keep smoke tooling auth-aware and aligned with the current local stack.

## Implementation Notes

- Preferred approach: codify the scenario matrix first in tests and smoke
  tooling, then update instruction docs to describe the same behavior.
- Existing pattern to mirror:
  - `instructions/08-quality/testing-strategy.md`
  - `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- Avoid:
  - muting failing tests without replacing them with explicit new expectations
  - leaving any budget policy ambiguity behind

## Acceptance Criteria

- [ ] All chat docs agree that hotel search requires destination and dates, with
      budget as an optional refinement
- [ ] A supported scenario matrix is documented and referenced by tests and
      smoke tooling
- [ ] Stale or missing chat planning references are removed or replaced
- [ ] Existing failing tests caused by contract drift are updated to the
      intended behavior instead of skipped or weakened

## Verification / Tests

- Run: `venv\Scripts\python.exe -m pytest tests\orchestrator\test_eval_conversations.py tests\orchestrator\test_service.py -q`
- Run: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled`
- Manually verify: docs and smoke expectations describe the same slot rules and
  release matrix

## Docs To Update

- `docs/README.md`
- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/08-quality/testing-strategy.md`
- `instructions/CHANGELOG.md`

## Definition of Done

- The repo has a single documented chat contract and matching smoke/test
  expectations.

## Open Questions / Assumptions

- Assumption: when item type is unknown, search-type clarification should happen
  before any optional refinement such as budget.
