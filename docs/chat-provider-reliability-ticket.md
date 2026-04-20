# Ticket: Harden provider-assisted planner/composer reliability and operational behavior

## Outcome / Goal

Make planner/composer reliable enough to be the primary production chat
experience, with explicit runtime tuning, diagnostics, and degradation behavior
that preserve naturalness instead of causing inconsistent path switching.

## Why / Context

Provider connectivity and model resolution have already been restored for local
development, but the live audit still showed:

- long turn times on otherwise valid requests
- `planner_status=failed` or `composer_status=failed` on supported flows
- `tool_timeout` on valid hotel searches
- circuit-open behavior during prolonged scenario runs

Provider assistance is the selected production-default experience, so this is a
release blocker rather than a low-priority improvement.

## In Scope

- Review and tune structured-stage timeout, cooldown, and failure-threshold
  behavior for current provider modes
- Separate local/dev-only timeout floors from production-facing expectations
  where needed
- Reduce avoidable planner/composer failures on supported flows
- Ensure recommendation timeout handling and provider-stage degradation are
  observable and actionable
- Add focused provider-runtime tests and runbook updates

## Out of Scope

- New provider integrations
- Replacing the current circuit-breaker design with a new orchestration
  framework
- Reworking non-provider deterministic extraction logic except where needed for
  reliable alignment

## Repo Context To Read First

- `instructions/04-llm-orchestrator/orchestrator-overview.md`
- `instructions/07-infra-ops/local-dev.md`
- `instructions/07-infra-ops/observability.md`
- `instructions/07-infra-ops/runbooks.md`

## Relevant Files / Modules

- `apps/api/app/services/travel_tom_agent.py`: provider stages, timeout floors,
  circuit behavior, diagnostics
- `apps/api/app/services/orchestrator/llm_provider.py`: provider client setup
  and health probing
- `apps/api/app/services/orchestrator/providers/ollama.py`: structured Ollama
  request path
- `apps/api/app/core/config.py`: runtime knobs and provider defaults
- `tests/orchestrator/test_llm_provider.py`: provider timeout and health tests
- `tests/api/test_chat.py`: API-level diagnostics expectations

## Current Behavior

Provider-assisted flows can still degrade on valid requests because stage
failure, timeout, and cooldown behavior are not yet tuned to the release
scenario matrix.

## Desired Behavior

- Supported provider-assisted turns complete reliably enough to be the primary
  user experience.
- Failures degrade safely but do not thrash between planner/composer modes or
  linger in open-circuit states unnecessarily.
- Operational docs explain how to diagnose provider latency, stage failures, and
  circuit-open events.

## Constraints / Non-negotiables

- Keep deterministic fallback intact.
- Keep provider-stage diagnostics exposed in local/dev headers.
- Do not hide failures by silently downgrading product expectations.
- Avoid machine-specific magic values without documenting the environment
  assumptions behind them.

## Implementation Notes

- Preferred approach: tune existing timeouts, thresholds, and provider-health
  handling against the audited scenario matrix and current provider configs.
- Existing pattern to mirror:
  - `travel_tom_agent.py` stage-specific circuit handling
  - current `X-TravelTom-*` diagnostic headers
- Avoid:
  - removing diagnostics to make failures less visible
  - allowing local-only timeout floors to define production expectations

## Acceptance Criteria

- [ ] Provider-assisted supported flows in the release matrix complete without
      persistent `planner_status=failed` or `circuit_open` behavior under a
      warmed local/dev setup
- [ ] Valid hotel search flows do not hit avoidable `tool_timeout` in normal
      local/dev verification conditions
- [ ] Runtime docs clearly describe provider timeout floors, failure thresholds,
      and expected `X-TravelTom-*` diagnostics
- [ ] Provider-runtime tests cover the tuned timeout and degradation behavior

## Verification / Tests

- Run: `venv\Scripts\python.exe -m pytest tests\orchestrator\test_llm_provider.py tests\api\test_chat.py -q`
- Run: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email <generated>`
- Manually verify: inspect `X-TravelTom-*` headers and logs over a
  multi-scenario run for planner/composer stability

## Docs To Update

- `instructions/07-infra-ops/local-dev.md`
- `instructions/07-infra-ops/observability.md`
- `instructions/07-infra-ops/runbooks.md`
- `instructions/CHANGELOG.md` if instruction docs change

## Definition of Done

- Provider-assisted runtime is operationally understandable and stable enough to
  meet the release matrix.

## Open Questions / Assumptions

- Assumption: local/dev verification remains the required pre-release bar, but
  production settings may use different provider capacity and tighter latency
  targets.
