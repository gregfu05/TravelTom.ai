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
- if unsure, fall back to the deterministic message supplied by backend

## Deterministic guardrails

- Greetings and social turns do not mutate trip slots.
- Meta questions stay conversational.
- Repair turns do not auto-trigger a new search.
- Hotel slot gating waits for destination, dates, and budget.
- Restaurant and activity slot gating wait for destination.
- Follow-up phrases such as `show me more` and `cheaper` reuse carried query state.
- Interest extraction is token-aware and negation-aware.
- Natural one-shot requests such as
  `Hotels in Lisbon from 2026-05-10 to 2026-05-20 under 2000 EUR`
  must work without planner help.

## Provider degradation

- Planner failures log as `planner_execution_failed` or `planner_unavailable`.
- Provider stage circuit events log as:
  - `provider_stage_succeeded`
  - `provider_stage_failed`
  - `provider_stage_skipped`
- Deterministic fallback copy must remain acceptable even when composition is disabled.
