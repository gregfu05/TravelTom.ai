# Open Questions

This file tracks ambiguities or missing details from the design document.

Decision lock timestamp: 2026-02-06.
Use these values as the active defaults for implementation until explicitly changed.

## 1. Coverage requirement ("Coverage >= N candidates")

Status: Provisional default (active).

Decision:
- Minimum coverage per requested category: `N = 5`.
- Minimum total results per request: `M = 20`.
- Evaluation pass condition: at least 95% of evaluated sessions meet both thresholds.

Change control:
- Revisit only after a benchmark refresh or explicit product decision.

## 2. Flight data realism in MVP

Status: Provisional default (active).

Decision:
- MVP uses dummy flights with realistic-looking metadata and static pricing.
- Final keeps static demo pricing unless a real provider integration is explicitly approved.
- Flight recommendations must remain deterministic for a fixed seed dataset.

Change control:
- Revisit only if external provider integration enters scope.

## 3. Personalization persistence

Status: Provisional default (active).

Decision:
- MVP: session-level preferences only.
- Final: session-level remains default.
- Account-level persistence is disabled until authentication and deletion SLA controls are fully enabled.

Change control:
- Revisit when account auth and privacy controls are completed.
