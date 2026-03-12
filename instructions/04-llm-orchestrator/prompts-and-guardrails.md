# Prompts and Guardrails

## System-level guardrails

- The assistant is a travel orchestrator, not a recommendation source.
- Recommendations must come only from the recommendation tool response.
- Tool input and output contracts are always schema-validated.
- If the agent transcript is missing a safe grounded answer, fail safe and continue with deterministic fallback logic.
- API routes enter through `TravelTomAgent`, which selects either `chat` or
  `direct_recommendation` mode; both modes are built with LangChain `create_agent`.

## Chat-agent system prompt

The shared chat agent receives:

- a bounded system prompt
- one hidden runtime-context message containing validated `SessionState` JSON
- the latest user message
- one allowed tool: `recommendation_query`

The system prompt constrains the model to two behaviors only:

- ask a short clarification question, or
- call `recommendation_query` and then summarize only grounded tool results

Hard instructions in the prompt:

- `recommendation_query` is the only recommendation source
- never invent items, prices, or availability
- if the tool returns no results, say so plainly
- if the user message is vague, ask only for the missing trip details

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
- Query filter guardrail normalizes item types to `destination|hotel|flight`.
- Recommendation ranking version stays deterministic (`heuristic-v1`).
- `OrchestratorService` normalizes the final transcript and only trusts validated
  tool artifacts for recommendation data.
- Direct recommendation mode bypasses conversational composition and returns only
  schema-validated tool output.

## Fallback response requirements

- Chat-model or agent execution failure:
  - Use deterministic extraction plus direct deterministic tool execution when
    the fallback guardrail says a search is still appropriate.
- Invalid request after tool-call validation:
  - Ask for the missing travel details in conversational branded copy.
- Tool timeout:
  - Return retry-safe deterministic prompt.
- Invalid tool output:
  - Return safe deterministic invalid-payload prompt.
- Empty tool results:
  - Return explicit no-strong-match message and ask for tighter constraints.
- Missing or blank final agent message:
  - Use deterministic fallback copy based on the validated tool artifact.

Hard grounding rules for replies:

- Never invent recommendation items, prices, availability, or destination facts.
- Mention recommendations only if they appear in validated `RecommendationToolResponse.results`.
- If there are no results, do not imply that hidden or unavailable options exist.
- Tool timeout, invalid tool payload, and unexpected tool failures remain deterministic and do not depend on model-authored recovery text.
- The direct recommendation endpoint remains tool-only and cannot generate model-authored recommendations.
