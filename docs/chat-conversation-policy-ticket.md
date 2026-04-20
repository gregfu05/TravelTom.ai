# Ticket: Fix clarification policy and conversation flow naturalness

## Outcome / Goal

Make the assistant ask the correct next question, keep repairs and refinements
on topic, and maintain a natural multi-turn flow across planner-assisted and
fallback modes.

## Why / Context

Conversation quality defects are now more visible because provider connectivity
is restored. The live audit still surfaced:

- preference-led exploration asking for the wrong missing slot in some runs
- destination-and-date statements asking for budget instead of recommendation
  type
- empty-result recovery that stays stuck in weak clarification loops
- copy divergence between deterministic and composed clarification paths

These behaviors make the assistant feel erratic even when the raw slot state is
otherwise recoverable.

## In Scope

- Fix missing-slot ordering so search-type clarification occurs before budget
  when item type is unknown
- Fix preference-led exploration carry-forward so
  `I like nightlife and food` followed by `show me options` consistently asks
  for destination first
- Ensure composer-authored clarification text is accepted only when it matches
  backend-computed next-slot policy
- Improve post-empty-results relaxation logic so the assistant widens or re-asks
  in a useful way without losing context
- Tighten repair-turn handling so corrections such as
  `not restaurants, more like sightseeing` remain natural and do not reset the
  thread

## Out of Scope

- Provider timeout tuning and circuit-breaker thresholds
- Frontend rendering changes beyond what is needed to reflect backend behavior

## Repo Context To Read First

- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/05-frontend/ux-flows.md`
- `instructions/08-quality/testing-strategy.md`

## Relevant Files / Modules

- `apps/api/app/services/orchestrator/policies.py`: clarification rules,
  messages, repair handling
- `apps/api/app/services/orchestrator/service.py`: turn flow, composition
  alignment, outcome handling
- `apps/api/app/services/orchestrator/response_assembler.py`: deterministic
  grounded assistant copy
- `tests/orchestrator/test_service.py`: clarification and repair behavior
- `tests/orchestrator/test_eval_conversations.py`: conversation-level contract
- `scripts/smoke-chat-runtime.ps1`: live flow assertions

## Current Behavior

Clarification priorities and naturalness vary by runtime path, leading to wrong
asks and awkward recovery behavior.

## Desired Behavior

- The assistant always asks the most useful next slot according to backend
  policy.
- Preference-led exploration remains coherent across follow-up turns.
- Repair and empty-result turns preserve the same active recommendation thread
  unless the user clearly pivots.
- Provider-assisted composition cannot override backend clarification intent with
  a mismatched slot ask.

## Constraints / Non-negotiables

- Backend-computed missing-slot logic remains authoritative.
- Composer clarification text that conflicts with backend slot policy must be
  rejected.
- Do not require budget for first-pass hotel search.
- Keep follow-up carry-forward behavior explicit and testable.

## Implementation Notes

- Preferred approach: centralize clarification precedence and make
  planner/composer alignment checks stricter rather than looser.
- Existing pattern to mirror:
  - `rejected_misaligned_clarification` diagnostics
  - current repair-turn handling paths
- Avoid:
  - patching individual phrases without fixing the underlying precedence rules
  - letting provider-authored copy silently override deterministic slot policy

## Acceptance Criteria

- [ ] `I am going to Lisbon next weekend` asks what kind of recommendations the
      user wants, not for budget
- [ ] `I like nightlife and food` then `show me options` consistently asks for
      destination in provider-assisted and fallback paths
- [ ] `not restaurants, more like sightseeing` keeps the session in the same
      activity-oriented recommendation thread
- [ ] After empty results, replies like `anything works`, `cheaper`, and
      `show me more` produce sensible next-step behavior without restarting
      context
- [ ] Targeted tests and smoke assertions cover these flows

## Verification / Tests

- Run: `venv\Scripts\python.exe -m pytest tests\orchestrator\test_service.py tests\orchestrator\test_eval_conversations.py -q`
- Run: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled`
- Run: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email <generated>`

## Docs To Update

- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/CHANGELOG.md` if instruction docs change

## Definition of Done

- Clarification ordering and repair behavior are stable across runtime modes and
  covered by tests and smoke tooling.

## Open Questions / Assumptions

- Assumption: when item type is unknown, the next question should be the
  recommendation type before any optional refinement such as budget.
