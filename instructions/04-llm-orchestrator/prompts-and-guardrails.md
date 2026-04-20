# Prompts and Guardrails

## Core rules

- The model is not the source of recommendations.
- The backend owns recommendation execution and validation.
- Persisted state changes must pass schema validation.
- Provider-backed planning/composition are optional; correctness must survive without them.
- `/api/v1/recommendations/query` is deterministic and model-free.

## Planner contract

The planner receives:

- current validated `SessionState`
- bounded recent transcript replay
- deterministic extraction hints
- latest user message

The planner may propose only:

- `intent`
- `should_call_recommendation_tool`
- `clarification_message`
- `state_patch`
- `query_controls`

Planner hard rules:

- return JSON only
- never invent recommendations, prices, or availability
- treat deterministic hints as advisory
- use `state_patch` only for grounded slot updates
- do not emit unsupported state keys
- leave execution control to backend code

## Composer contract

The composer receives:

- validated current state
- bounded recent transcript replay
- latest user message
- grounded recommendation records
- deterministic fallback text

Composer hard rules:

- return JSON only in the composed-response schema
- mention only grounded recommendation records
- never invent items, prices, or destination facts
- when naming multiple surfaced recommendations, keep surfaced order and do not
  skip higher-ranked items inside the named subset
- do not introduce score, ranking, or match-quality claims unless they are
  directly grounded in the supplied recommendation data
- if unsure, fall back to the deterministic message supplied by backend

## Deterministic guardrails

- Greetings and social turns do not mutate trip slots.
- Meta questions stay conversational.
- Repair turns do not auto-trigger a new search.
- Hotel slot gating waits for destination and dates. Budget is an optional
  refinement input for first-pass hotel retrieval.
- Generic trip setup with destination and dates but no item type should ask for
  recommendation type before any optional budget refinement.
- Restaurant and activity slot gating wait for destination.
- Follow-up phrases such as `show me more` and `cheaper` reuse carried query state.
- Vague replies after empty or duplicate-only results should preserve the active
  recommendation thread instead of discarding prior query context.
- Interest extraction is token-aware and negation-aware.
- Unsupported flight requests must not mutate persisted trip constraints, even
  if provider planning is enabled.
- Composer-authored clarification text must align with the backend-computed
  missing slot or fall back to deterministic copy.
- Deterministic backend-owned copy may use a small curated set of semantically
  equivalent variants so disabled/fallback runs stay natural without changing
  slot policy or grounded meaning.
- Natural one-shot requests such as
  `Hotels in Lisbon from 2026-05-10 to 2026-05-20 under 2000 EUR`
  and `Santa Barbara May 10-20, 2000 EUR, hotels`
  must work without planner help.

## Provider degradation

- Planner failures log as `planner_execution_failed` or `planner_unavailable`.
- Provider stage circuit events log as:
  - `provider_stage_succeeded`
  - `provider_stage_failed`
  - `provider_stage_skipped`
- Deterministic fallback copy must remain acceptable even when composition is disabled.
