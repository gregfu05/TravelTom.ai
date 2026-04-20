# Ticket: Expand automated coverage and live E2E verification for chat release readiness

## Outcome / Goal

Turn the audit scenario matrix into repeatable automated and manual release
checks so regressions are caught before release instead of during exploratory
testing.

## Why / Context

Current coverage is strong in parts of the stack, but it did not fully prevent
the defects found in live audit. Release readiness needs explicit regression
coverage for messy user input, unsupported requests, clarification order,
provider-assisted behavior, and planner UI parity.

## In Scope

- Expand backend tests for the audited scenario coverage
- Extend `scripts/smoke-chat-runtime.ps1` to cover the agreed release matrix and
  assert planner/composer diagnostics where appropriate
- Add or extend frontend planner verification for live-backend parity where
  feasible, while keeping existing mocked E2E coverage
- Define the manual release checklist for real-backend planner verification
- Ensure auth-aware smoke scripts reflect the current local stack

## Out of Scope

- Broad frontend redesign
- New test infrastructure outside the current pytest, PowerShell smoke, Vitest,
  and Playwright stack

## Repo Context To Read First

- `instructions/08-quality/testing-strategy.md`
- `instructions/05-frontend/ux-flows.md`
- `instructions/07-infra-ops/local-dev.md`

## Relevant Files / Modules

- `scripts/smoke-chat-runtime.ps1`: live chat release matrix
- `scripts/smoke-api.ps1`: local API smoke baseline and auth assumptions
- `tests/orchestrator/`: backend scenario coverage
- `tests/api/test_chat.py`: API-level chat contract
- `apps/web/e2e/planner-smoke.spec.ts`: planner E2E baseline
- `apps/web/src/features/planner/components/ChatView/ChatView.test.tsx`:
  frontend chat rendering behavior

## Current Behavior

Coverage exists, but not enough of the live defect matrix is encoded as release
checks. Some smoke scripts also lag the current auth-enabled local stack.

## Desired Behavior

- The audited scenario matrix is executable in CI/local release verification.
- Auth-aware API smoke and planner E2E checks reflect the current app behavior.
- Release readiness is decided from explicit pass/fail evidence instead of ad
  hoc exploration.

## Constraints / Non-negotiables

- Keep smoke scripts runnable locally.
- Preserve mocked frontend E2E coverage while adding real-backend release
  verification guidance.
- Do not let live E2E be the only place correctness is asserted.
- Keep the release checklist short enough to be rerun during normal iteration.

## Implementation Notes

- Preferred approach: encode the highest-signal audited scenarios in backend
  tests and smoke tooling first, then keep frontend live verification small but
  meaningful.
- Existing pattern to mirror:
  - current planner smoke flow
  - auth-aware chat smoke tooling
- Avoid:
  - pushing too much correctness into UI-only verification
  - keeping stale unauthenticated smoke assumptions in the default local path

## Acceptance Criteria

- [ ] Backend automated coverage includes the audited defect scenarios from this
      ticket set
- [ ] `scripts/smoke-chat-runtime.ps1` asserts the release matrix, including
      provider-assisted clarification and refinement flows
- [ ] `scripts/smoke-api.ps1` reflects the auth-enabled local stack or is
      explicitly scoped to unauthenticated endpoints only
- [ ] Planner UI verification includes at least one real-backend supported
      recommendation flow and one continuity/recovery flow in the release
      checklist
- [ ] Testing docs list the exact commands and manual checks required before
      release

## Verification / Tests

- Run: `venv\Scripts\python.exe -m pytest tests\orchestrator tests\api\test_chat.py -q`
- Run: `pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000`
- Run: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email <generated>`
- Run: `cd apps\web && npm run test:ci`
- Manually verify: signup/login plus planner chat against the real backend for
  one happy path and one refinement/recovery path

## Docs To Update

- `instructions/08-quality/testing-strategy.md`
- `instructions/07-infra-ops/local-dev.md`
- `docs/README.md`
- `instructions/CHANGELOG.md` if instruction docs change

## Definition of Done

- The release matrix is encoded in tests, smokes, and a manual checklist that
  another engineer can rerun without extra context.

## Open Questions / Assumptions

- Assumption: a small real-backend UI release checklist is sufficient because
  most chat correctness should be locked at backend and smoke-test layers.
