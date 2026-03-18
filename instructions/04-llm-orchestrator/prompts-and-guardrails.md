# Prompts and Guardrails

## System-level guardrails

- The assistant is a travel orchestrator, not a recommendation source.
- Recommendations must come only from the recommendation tool response.
- Tool input and output contracts are always schema-validated.
- If chat-agent execution misses a safe grounded answer, fail safe and continue
  with deterministic fallback logic.
- API routes enter through `TravelTomAgent`, which selects either:
  - chat `create_agent` orchestration for `/api/v1/chat`
  - direct LangChain `create_agent` recommendation mode for
    `/api/v1/recommendations/query`

## Chat agent prompt

The chat agent receives bounded context that includes:

- validated `SessionState` JSON in a hidden system message
- deterministic carry-forward recommendation context in a hidden system message
- bounded recent transcript replay from persisted messages
- the latest user message

Hard chat-agent instructions:

- use recent transcript plus state to avoid re-asking for captured details
- on underspecified follow-ups, preserve prior recommendation intent unless the
  user explicitly overrides it
- if clarification is needed, ask for one next-most-useful missing detail
- never invent recommendation items, prices, or availability
- recommendation names and travel facts must come only from validated tool output

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
- Deterministic extraction runs before chat-agent invocation.
- Deterministic carry-forward helpers resolve the effective query text and item
  type for elliptical refine turns before the agent runs.
- Query filter guardrail normalizes item types to `destination|hotel|flight`.
- Recommendation ranking version stays deterministic (`heuristic-v1`).
- `SessionState.conversation` tracks `last_requested_slots` and
  `last_user_intent` so clarification stays progressive across turns.
- `SessionState.conversation.last_recommendation_item_type` and
  `last_recommendation_query` preserve recommender carry-forward semantics
  across follow-up turns.
- `OrchestratorService` only trusts validated recommendation payloads for
  recommendation data and destination-specific claims.
- Direct recommendation mode bypasses conversational composition and returns only
  schema-validated tool output.

## Fallback response requirements

- Chat-agent execution failure:
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
- Missing or blank final agent message:
  - Use deterministic fallback copy based on the validated tool artifact and
    current state.

Hard grounding rules for replies:

- Never invent recommendation items, prices, availability, or destination facts.
- Mention recommendations only if they appear in validated `RecommendationToolResponse.results`.
- If there are no results, do not imply that hidden or unavailable options exist.
- Tool timeout, invalid tool payload, and unexpected tool failures remain deterministic and do not depend on model-authored recovery text.
- The direct recommendation endpoint remains tool-only and cannot generate model-authored recommendations.
