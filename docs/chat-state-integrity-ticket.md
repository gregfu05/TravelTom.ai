# Ticket: Fix slot extraction and session-state integrity for varied user input

## Outcome / Goal

Make slot extraction and state persistence robust on realistic user phrasing so
natural requests do not lose constraints or corrupt session state.

## Why / Context

The live audit surfaced concrete state bugs that are blocking production
correctness:

- bare trailing budget phrasing was dropped from a natural one-shot hotel
  request
- typo-heavy input overcaptured destination instead of dates
- unsupported flight requests still mutated destination and dates
- vague follow-ups after empty results lost useful carried query context

These are backend correctness issues, not just copy or UX issues.

## In Scope

- Fix budget extraction for natural inline phrasing such as
  `Santa Barbara May 10-20, 2000 EUR, hotels`
- Improve noisy destination/date parsing so typo-heavy inputs do not absorb
  relative-date fragments into destination
- Prevent unsupported flight requests from mutating planning state
- Preserve and merge carried recommendation query state more safely on vague
  follow-ups after empty results
- Add targeted extraction and state-transition tests for audited scenarios

## Out of Scope

- Composer copy style improvements unrelated to state correctness
- New NLP dependencies or large extraction-framework changes

## Repo Context To Read First

- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/08-quality/testing-strategy.md`

## Relevant Files / Modules

- `apps/api/app/services/orchestrator/extraction.py`: extraction logic,
  carry-forward shaping, unsupported-intent detection
- `apps/api/app/services/orchestrator/turn_preparer.py`: deterministic hints and
  planner merge path
- `apps/api/app/schemas/state.py`: canonical session-state contract
- `tests/orchestrator/test_extraction.py`: extraction unit coverage
- `tests/orchestrator/test_service.py`: session-state and conversation-flow
  integration coverage

## Current Behavior

- Natural complete requests can lose budget.
- Noisy phrasing can corrupt `constraints.destination`.
- Unsupported requests can still patch `SessionState`.
- Empty-results follow-ups can lose active recommendation-thread context.

## Desired Behavior

- Budget, destination, and dates are extracted correctly from supported one-shot
  requests.
- Unsupported requests may be understood conversationally but do not mutate
  unsupported trip state.
- Follow-up state remains grounded to the active recommendation thread unless
  the user explicitly restarts intent.

## Constraints / Non-negotiables

- Keep `SessionState` validation strict.
- Do not allow weak inferred phrases to overwrite already valid slots.
- Do not let unsupported flight intent persist route-like state into the travel
  planner context.
- Do not regress explicit date or destination extraction that already works.

## Implementation Notes

- Preferred approach: tighten deterministic extraction and pre-state-patch
  filtering before planner output is merged.
- Existing pattern to mirror:
  - guarded destination extraction
  - schema-validated state patch flow
- Avoid:
  - ad hoc regex additions that create new false positives
  - allowing planner state patches to reintroduce filtered unsupported state

## Acceptance Criteria

- [ ] `Hotels in Santa Barbara from 2026-05-10 to 2026-05-20 under 2000 USD`
      persists the intended budget
- [ ] `Santa Barbara May 10-20, 2000 EUR, hotels` persists the intended budget
- [ ] `need smth chill in lisbn nxt wknd` resolves to destination `Lisbon` plus
      dates, or asks for dates without corrupting destination
- [ ] `need smth chill in lisbn nxt wknd` must not persist
      `next weekend in Lisbon` as destination
- [ ] `Find me flights from Paris to Lisbon next weekend` does not persist
      destination, dates, or route state into the planner session
- [ ] `anything works` after empty hotel results does not discard the active
      recommendation thread or create a misleading fresh-query state
- [ ] New tests cover each audited defect

## Verification / Tests

- Run: `venv\Scripts\python.exe -m pytest tests\orchestrator\test_extraction.py tests\orchestrator\test_service.py -q`
- Manually verify: live `/api/v1/chat` state snapshots for the audited scenarios

## Docs To Update

- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/CHANGELOG.md` if instruction docs change

## Definition of Done

- The audited extraction and state defects are reproducibly fixed and locked
  with tests.

## Open Questions / Assumptions

- Assumption: vague relaxation replies like `anything works` should relax the
  prior recommendation thread instead of starting a brand-new unrelated query.
