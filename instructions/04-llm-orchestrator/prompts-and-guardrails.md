# Prompts and Guardrails

## System-level guardrails

- The assistant is a travel orchestrator, not a recommendation source.
- Recommendations must come only from the recommendation tool response.
- Tool input and output contracts are always schema-validated.
- If any structured model output is invalid, fail safe and continue with deterministic fallback logic.

## Planner prompt (LLM-first decisioning)

Planner context is built from:

- Current `SessionState` JSON (validated persisted state).
- Latest user message.
- Current max-results policy.

Planner must return structured JSON matching `LLMOrchestrationPlan`:

- `intent`: `recommend|refine|clarify`
- `should_call_recommendation_tool`: `bool`
- `clarification_message`: required when not calling tool
- `state_patch`: partial `SessionState` updates
- `query_controls`: normalized `RecommendationQuery` controls

If planner output is invalid or planner invocation fails, orchestration falls back to deterministic guardrail planning.

## Response-composer prompt (grounded copy)

Composer context is built from:

- Current `SessionState` JSON.
- Latest user message.
- Validated recommendation result list (or explicit `NO_RESULTS`).
- Explicit deterministic fallback copy.

Composer must return:

```json
{"assistant_message": "string"}
```

If composer output is invalid or composer invocation fails, orchestration returns the provided deterministic fallback message.

## Deterministic guardrails kept in runtime

- Structured state patch merge validates against `SessionState`.
- Deterministic extraction still enriches missed constraints from user text.
- Query filter guardrail normalizes item types to `destination|hotel|flight`.
- Recommendation ranking version stays deterministic (`heuristic-v1`).

## Fallback response requirements

- Planner failure/invalid output:
  - Use deterministic fallback planner.
- Invalid request after schema mapping:
  - Ask for destination, dates, and budget.
- Tool timeout:
  - Return retry-safe timeout prompt.
- Invalid tool output:
  - Return safe invalid-payload prompt.
- Empty tool results:
  - Return explicit no-strong-match message and ask for tighter constraints.
- Composer failure/invalid output:
  - Use deterministic results/clarification fallback copy.
