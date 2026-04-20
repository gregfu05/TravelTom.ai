# Orchestrator Overview

## Responsibilities

- Run `/api/v1/chat` through a deterministic backend-owned orchestration flow.
- Treat provider-backed planning and composition as optional enhancements.
- Keep recommendation execution, state mutation, and safety checks in backend code.
- Persist grounded recommendation snapshots and validated `SessionState`.
- Ensure provider failure degrades to a still-correct deterministic flow.

## Runtime modules

- `apps/api/app/services/travel_tom_agent.py`
  - Route-facing adapter used by `/chat` and `/recommendations/query`.
  - Wires planner/composer structured clients plus the shared recommendation tool.
  - Applies provider stage circuit-breaking for planner and composer.
  - Emits per-turn planner/composer diagnostics for local/dev verification.
- `apps/api/app/services/orchestrator/service.py`
  - Main coordinator for turn handling, clarification continuity, and response mapping.
- `apps/api/app/services/orchestrator/turn_preparer.py`
  - Deterministic extraction, planner invocation/validation, and slot gating.
- `apps/api/app/services/orchestrator/decision_engine.py`
  - Chooses direct runtime handling versus agent-path handling.
- `apps/api/app/services/orchestrator/recommendation_runner.py`
  - Builds validated `RecommendationQuery` and runs deterministic search execution.
- `apps/api/app/services/orchestrator/response_assembler.py`
  - Converts grounded results into backend-owned assistant copy with controlled
    deterministic variation.
- `apps/api/app/services/orchestrator/policies.py`
  - Clarification rules, prompt builders, and deterministic guardrails.
- `apps/api/app/services/orchestrator/extraction.py`
  - Slot extraction, interest capture, carry-forward shaping, and repair/meta detection.
- `apps/api/app/services/recommendation_runtime.py`
  - Shared runtime recommendation tool backed by seeded `catalog_items`.

## Chat flow

1. `/api/v1/chat` loads persisted state and a bounded recent transcript window.
2. `TurnPreparer` applies deterministic extraction to the latest user turn.
3. If a planner provider is configured and healthy, the planner receives:
   - validated current state
   - bounded recent transcript
   - deterministic hint state
   - raw user text
4. Planner output is schema-validated and merged on top of deterministic
   extraction through backend code only.
5. Deterministic guardrails decide whether the turn is:
   - clarification-only
   - search-ready
   - unsupported
6. If search-ready, backend code builds `RecommendationQuery` and executes the
   recommender directly.
7. Result copy is assembled deterministically, with optional provider-backed
   grounded composition when healthy and validated against surfaced results.
8. The API persists updated state, transcript messages, and the latest grounded
   recommendation snapshot.
9. In local/dev, `/api/v1/chat` also returns planner/composer diagnostics in
   `X-TravelTom-*` headers so degraded execution is visible immediately.

## Direct recommendation flow

1. `/api/v1/recommendations/query` resolves the same `TravelTomAgent`.
2. The route calls `handle_recommendation_query(...)`.
3. The backend executes the shared deterministic recommendation tool directly.
4. The route returns validated `RecommendationResponse` without model-authored text.

## Deterministic guarantees

- Recommendation items only come from validated `RecommendationToolResponse`.
- The backend, not the model, decides when to search.
- Model-authored tool arguments are not required for `/api/v1/chat`.
- Hotel searches require destination and dates for first-pass retrieval.
- Budget remains an optional hotel refinement input.
- Restaurant and activity searches require destination.
- Follow-up turns preserve carried query and item-type state in
  `SessionState.conversation`.
- Empty-result and duplicate-only flows stay explicit and grounded.
- Backend-owned copy can vary across a curated semantic-equivalent set while
  preserving the same slot and recommendation semantics.

## Provider behavior

- `disabled`: deterministic-only orchestration.
- `ollama` / `openai`: deterministic orchestration plus optional planner/composer.
- Planner and composer each have:
  - stage-specific timeout budgets
  - failure thresholds
  - cooldown windows
- On Ollama, TravelTom prefers the native structured `/api/chat` flow before the
  OpenAI-compatible endpoint for planner/composer requests.
- In local/dev, slow local Ollama models use higher effective timeout floors for
  planner/composer stages so realistic prompts can complete.
- Provider failures log explicitly and fall back safely.

## Failure handling

- Planner failure or invalid output:
  - log it and continue with deterministic guardrails
- Composer failure:
  - return deterministic grounded copy
- Composer output that drifts from surfaced result names/order or invents
  unsupported ranking rationale is rejected and replaced with backend-owned copy
- Recommendation timeout/failure:
  - return safe deterministic fallback copy
- Invalid state patch or tool payload:
  - reject it and continue safely
