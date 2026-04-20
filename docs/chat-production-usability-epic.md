# Ticket: Make chat production-usable across provider-assisted and fallback flows

## Outcome / Goal

Bring `/api/v1/chat` to a production-usable state where supported travel
planning requests are handled naturally, slot and state persistence remain
correct across varied user input, and provider-assisted flows are reliable
enough to be the primary user experience with deterministic fallback remaining
safe.

## Why / Context

Recent live audit passes confirmed that the chat feature can handle some common
travel-planning flows, but it is still not robust enough for production use.
The main blocking defect classes are:

- contract drift across docs, tests, smoke scripts, and runtime rules
- state and extraction bugs on realistic user phrasing
- clarification and repair behavior that is inconsistent across runtime paths
- provider-assisted instability and latency that can change behavior turn to
  turn

Concrete live findings that motivated this epic:

- bare inline budget phrasing can be dropped from complete hotel requests
- unsupported flight requests can still mutate destination and dates
- preference-led exploration can ask for the wrong missing slot
- destination-and-date statements can ask for budget instead of search type
- typo-heavy input can corrupt `constraints.destination`
- provider-assisted turns can still fail, time out, or circuit-open under
  sustained scenario runs
- `docs/README.md` referenced a missing chat investigation artifact instead of
  a real ticket set

The repo already has the architectural pieces needed to fix this within the
current deterministic-orchestrator design. The remaining work is to align the
product contract, fix the audited defects, harden provider behavior, and lock
the scenario matrix into repeatable verification.

## In Scope

- Align chat contracts, docs, smoke scripts, and tests around one intended
  product behavior
- Fix slot extraction, carry-forward, and session-state integrity issues found
  in the live audit
- Fix clarification order, repair handling, and empty-result recovery so the
  conversation stays natural
- Harden planner/composer runtime reliability, tuning, and observability
- Expand automated and live verification for the audited scenario matrix
- Produce repo-native chat production-readiness ticket artifacts and doc links

## Out of Scope

- Replacing the current backend-owned orchestration architecture
- Adding new recommendation domains beyond hotel, restaurant, and activity
- Broad frontend redesign unrelated to planner correctness
- Migrating to a different provider platform or infra stack

## Repo Context To Read First

- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/07-infra-ops/local-dev.md`
- `instructions/07-infra-ops/observability.md`
- `instructions/08-quality/testing-strategy.md`

## Relevant Files / Modules

- `apps/api/app/services/orchestrator/`: extraction, slot gating, response
  policy, and recommendation execution
- `apps/api/app/services/travel_tom_agent.py`: planner/composer execution,
  timeout handling, circuit-breaking, diagnostics
- `tests/orchestrator/`, `tests/api/test_chat.py`, and
  `scripts/smoke-chat-runtime.ps1`: current chat verification baseline
- `apps/web/src/features/planner/`: planner UI rendering and session hydration
  behavior
- `docs/README.md`: docs index that should point to the new chat ticket set

## Current Behavior

- Deterministic and provider-assisted paths disagree on some clarification
  choices.
- Some natural complete requests still lose budget constraints.
- Unsupported requests can persist partial planning state.
- Provider-assisted quality is not yet reliable enough to be treated as the
  production-default experience.
- Chat docs currently disagree on whether hotel search requires budget.

## Desired Behavior

- Supported chat flows produce the same slot and state decisions regardless of
  whether planner/composer assist the turn.
- Provider-assisted flows are healthy and natural on the release scenario
  matrix.
- Deterministic fallback remains safe and acceptable whenever provider stages
  fail.
- Contracts, docs, smoke scripts, and tests all reflect the same intended
  behavior.
- Chat release readiness can be judged from repo-native artifacts without
  relying on prior chat context.

## Constraints / Non-negotiables

- Keep backend-owned recommendation execution and state validation intact.
- Do not let free-form model text become the source of truth for persisted
  state.
- Keep routers thin and shared contracts under `apps/api/app/schemas/`.
- Budget stays optional for first-pass hotel retrieval.
- Provider-assisted quality is a release blocker for supported flows.
- Update docs and tests in the same change when behavior changes.
- Keep each child ticket small enough to review independently.

## Implementation Notes

- Preferred approach: fix deterministic correctness and slot policy first, then
  make provider-assisted behavior align tightly to those backend decisions.
- Existing pattern to mirror:
  - `instructions/08-quality/agent-ticket-template.md`
  - `docs/azure-deployment-readiness-ticket.md`
- Avoid:
  - bundling broad refactors with behavior fixes
  - treating local-model instability as a reason to weaken the product contract
  - allowing unsupported intents to write trip-planning state
- Child tickets and order:
  1. `docs/chat-contract-alignment-ticket.md`
  2. `docs/chat-state-integrity-ticket.md`
  3. `docs/chat-conversation-policy-ticket.md`
  4. `docs/chat-provider-reliability-ticket.md`
  5. `docs/chat-release-verification-ticket.md`

## Acceptance Criteria

- [ ] All child tickets below are completed in order or with explicit dependency
      handling
- [ ] Supported provider-assisted chat scenarios pass with expected slot/state
      behavior
- [ ] Deterministic fallback remains safe on the same supported scenarios
- [ ] No known doc/test/runtime contract drift remains for chat
- [ ] Repo contains a stable chat production-readiness artifact referenced from
      `docs/README.md`

## Verification / Tests

- Run: `venv\Scripts\python.exe -m pytest tests\orchestrator tests\api\test_chat.py -q`
- Run: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled`
- Run: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email <generated>`
- Run: `cd apps\web && npm run test:ci`
- Manually verify: authenticated planner UI against the real backend for at
  least one hotel happy path and one recovery/refinement flow

## Docs To Update

- `docs/README.md`
- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/04-llm-orchestrator/prompts-and-guardrails.md`
- `instructions/04-llm-orchestrator/session-state-schema.md`
- `instructions/07-infra-ops/local-dev.md`
- `instructions/07-infra-ops/observability.md`
- `instructions/08-quality/testing-strategy.md`
- `instructions/CHANGELOG.md` if instruction docs change

## Definition of Done

- The child tickets are implemented, verified, and linked from the epic.
- Release-readiness evidence exists in repo-native form.
- Final summary captures changed behavior, verification, and any residual
  follow-ups.

## Open Questions / Assumptions

- Assumption: provider-assisted quality remains the target production user
  experience.
- Assumption: unsupported flight handling should refuse the request without
  mutating travel-planning state.
- Assumption: budget remains optional for first-pass hotel retrieval.
