# Prompts and Guardrails

## System-level guardrails

- The assistant is a travel orchestrator, not a recommendation source.
- Recommendations must come only from the recommendation tool response.
- Tool input and output contracts are always schema-validated.
- If planner or composer execution misses a safe grounded answer, fail safe and
  continue with deterministic fallback logic.
- API routes enter through `TravelTomAgent`, which selects either:
  - planner/composer chat orchestration for `/api/v1/chat`
  - direct LangChain `create_agent` recommendation mode for
    `/api/v1/recommendations/query`

## Planner prompt

The planner receives bounded prompt context that includes:

- validated `SessionState` JSON
- bounded recent transcript replay from persisted messages
- the latest user message
- the hard `max_results` limit for this turn

The planner must return JSON only with:

- `intent`
- `should_call_recommendation_tool`
- optional `clarification_message`
- `state_patch`
- `query_controls`

Hard planner instructions:

- use recent transcript plus state to avoid re-asking for captured details
- if clarification is needed, ask for one next-most-useful missing detail
- never invent recommendation items, prices, or availability
- only propose structured state updates that fit the strict state schema

## Composer prompt

The composer receives bounded prompt context that includes:

- validated `SessionState` JSON
- bounded recent transcript replay
- latest user message
- validated recommendation records only
- a deterministic fallback message

The composer must return JSON only in the form:

- `{"assistant_message": "..."}`

Hard composer instructions:

- recommendation names and travel facts must come only from validated tool output
- if clarifying, acknowledge newly captured details when useful
- do not repeat the same full clarification list when one next slot is enough
- if no recommendations exist, say so plainly and guide the user to tighten or adjust constraints

## Direct recommendation prompt

The direct recommendation agent uses a separate deterministic model and a system
prompt that forces exactly one `recommendation_query` call from the serialized
request payload. It does not author end-user recommendation text.

## Tool-grounding behavior

The recommendation LangChain tool is defined with `@tool` and returns:

- human-readable tool content for the model to ground on
- a schema-validated runtime artifact consumed by backend post-processing

The runtime artifact records:

- `status`: `success|timeout|invalid_payload|failure`
- validated `RecommendationToolResponse` on success
- normalized error codes/messages on failure

## Deterministic guardrails kept in runtime

- Deterministic extraction still enriches missed constraints from user text.
- Deterministic extraction runs before planner patch merging.
- Query filter guardrail normalizes item types to `destination|hotel|flight`.
- Planner state patches are merged with strict validation; invalid patches are ignored.
- Recommendation ranking version stays deterministic (`heuristic-v1`).
- `SessionState.conversation` tracks `last_requested_slots` and
  `last_user_intent` so clarification stays progressive across turns.
- `OrchestratorService` only trusts validated recommendation payloads for
  recommendation data and destination-specific claims.
- Direct recommendation mode bypasses conversational composition and returns only
  schema-validated tool output.

## Fallback response requirements

- Planner or composer execution failure:
  - Use deterministic extraction plus deterministic guardrail planning.
  - If the fallback plan still supports a search, run deterministic
    recommendation execution and deterministic grounded copy.
- Invalid request after tool-call validation:
  - Ask for the next most useful missing travel detail in conversational branded copy.
- Tool timeout:
  - Return retry-safe deterministic prompt.
- Invalid tool output:
  - Return safe deterministic invalid-payload prompt.
- Empty tool results:
  - Return explicit no-strong-match message and ask for tighter constraints.
- Missing or blank composer message:
  - Use deterministic fallback copy based on the validated tool artifact and
    current state.

Hard grounding rules for replies:

- Never invent recommendation items, prices, availability, or destination facts.
- Mention recommendations only if they appear in validated `RecommendationToolResponse.results`.
- If there are no results, do not imply that hidden or unavailable options exist.
- Tool timeout, invalid tool payload, and unexpected tool failures remain deterministic and do not depend on model-authored recovery text.
- The direct recommendation endpoint remains tool-only and cannot generate model-authored recommendations.
