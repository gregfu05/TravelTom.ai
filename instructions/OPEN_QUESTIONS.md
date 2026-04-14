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

## 2. Catalog metadata realism in MVP

Status: Provisional default (active).

Decision:
- MVP uses deterministic seed data for hotels, restaurants, and activities.
- Final keeps static demo metadata unless a real provider integration is explicitly approved.
- Recommendations must remain deterministic for a fixed seed dataset.

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

## 4. Local auth token lifecycle

Status: Provisional default (active).

Decision:
- Current end-to-end backend auth/session lifecycle is local TravelTom auth only.
- Absolute local bearer-token expiry default: `604800` seconds.
- Idle timeout default: `43200` seconds.
- Logout revokes only the current local bearer token.

Change control:
- Revisit when deployment/provider auth work is scheduled.
