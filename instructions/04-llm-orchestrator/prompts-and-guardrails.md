# Prompts and Guardrails

## System-level guardrails

- The assistant is a travel orchestrator, not a recommendation source.
- Recommendations must come only from the recommendation tool response.
- Tool input and output contracts are always schema-validated.
- Persisted `/chat` state may only change through a validated
  `LLMOrchestrationPlan.state_patch` merged by backend code.
- If chat-agent execution misses a safe grounded answer, fail safe and continue
  with deterministic fallback logic.
- API routes enter through `TravelTomAgent`, which selects either:
  - structured planning plus chat `create_agent` orchestration for
    `/api/v1/chat`
  - direct LangChain `create_agent` recommendation mode for
    `/api/v1/recommendations/query`
- Runtime orchestration is phased internally:
  - `TurnPreparer` prepares validated state and planning metadata
  - `RecommendationDecisionEngine` chooses direct handling versus agent execution
  - `RecommendationRunner` owns deterministic recommendation execution
  - `ResponseAssembler` normalizes recommendation outcomes before final reply composition

## Planner prompt

Before the chat agent runs, the planner receives:

- validated current `SessionState`
- bounded recent transcript replay
- raw latest user text
- deterministic extraction and carry-forward hints from `extraction.py`

Hard planner instructions:

- return JSON only matching `LLMOrchestrationPlan`
- keep it compact: single-line JSON, omit optional keys you are not setting
- treat deterministic hints as advisory, not authoritative
- on normal `/chat` turns, own the extraction of destination, dates, budget,
  item type, and clarification intent from natural language
- use `state_patch` for persisted state changes; never rely on free-form chat
  text to mutate state
- do not let greetings, meta questions, or repair turns fill trip constraints
  unless the surrounding context clearly supports it
- do not emit unsupported keys like `conversation`, `shortlist`, or itinerary
  fields inside `state_patch`; invalid planner keys must fall back
- if a safe recommendation search is not ready, return one next-most-useful
  clarification message
- capture natural phrases like `I want to go to Santa Barbara` and
  `Hotels in Santa Barbara May 10th to May 20th under 2000 euros` in
  `state_patch` instead of relying on deterministic regex persistence
- when prior validated state already has destination, dates, and budget, treat
  replies like `I want hotels to be honest` as item-type selection, not as a
  new destination
- never invent recommendation items, prices, or availability

## Chat agent prompt

The chat agent receives bounded context that includes:

- validated `SessionState` JSON in a hidden system message
- validated planner-shaped recommendation context in a hidden system message
- bounded recent transcript replay from persisted messages
- the latest user message

Hard chat-agent instructions:

- use recent transcript plus state to avoid re-asking for captured details
- on underspecified follow-ups, preserve prior recommendation intent unless the
  user explicitly overrides it
- while clarifying, preserve pending recommendation item type and carried query
  so the user does not need to restate `recommend`
- destination exploration may call `recommendation_query` from partial signal
  like vibe, trip length, or budget
- hotel searches still wait for destination, dates, and budget
- flight searches still wait for origin, destination, dates, and budget
- if the latest user turn supplies the final missing slot for an active
  recommendation flow, call `recommendation_query` immediately
- if clarification is needed, ask for one next-most-useful missing detail
- if destination, dates, and budget are known but item type is still unknown,
  ask a deterministic search-type clarification instead of dropping into a
  generic refine prompt
- if runtime already has a validated planner-backed search-ready reply to a
  pending slot or search-type clarification, backend may execute the grounded
  recommendation path directly instead of waiting on another model round-trip
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

- Deterministic extraction still enriches missed constraints from user text, but
  primarily as planner hint input and deterministic fallback state.
- Deterministic extraction runs before planner state merging and before
  chat-agent invocation.
- Deterministic fallback must not overwrite an existing valid destination from
  weak filler phrases or low-signal refinements such as `be honest`,
  `cheaper`, or `lower cost`.
- Interest extraction is token-aware and negation-aware:
  - `Santa Barbara` must not imply `bar` or `nightlife`
  - repair phrases like `not restaurants` must not add positive `food` interest
- Planner output is validated against `LLMOrchestrationPlan`, and
  `state_patch` merges through `apply_structured_state_patch(...)` before any
  updated state is persisted or shown to the chat agent.
- When planner output already contains the next clarification message, runtime
  may return that planner-backed clarification directly instead of invoking the
  chat agent to paraphrase the same step.
- Explicit `destination ...` extraction only accepts assignment-like forms such
  as `destination is Lisbon` or `destination: Lisbon`; conversational mentions
  of the word `destination` do not capture a place value.
- Bare destination extraction still accepts concise location replies like
  `Lisbon`, but rejects greetings and meta chat so those turns do not mutate
  trip slots or seed fake destination context.
- Deterministic carry-forward helpers resolve the effective query text and item
  type for elliptical refine turns and slot-filling clarification turns before
  the agent runs, and planner `query_controls` may refine those values when
  they validate cleanly.
- Deterministic follow-up carry-forward also recognizes lower-cost refinement
  phrasing like `lower cost` and `budget option` so fallback mode preserves the
  active hotel/flight thread instead of resetting destination state.
- Deterministic route extraction accepts natural flight replies like
  `Madrid to Lisbon` when flight context is active.
- Deterministic date and budget extraction accepts compact mixed trip messages
  like `Santa Barbara 10th May to 20th May 2000 euros` without treating the
  budget as a year or overwriting the destination with date-preface filler.
- Query filter guardrail normalizes item types to `destination|hotel|flight`.
- Recommendation ranking version stays deterministic (`heuristic-v1`).
- `SessionState.conversation` tracks `last_requested_slots` and
  `last_user_intent` so clarification stays progressive across turns.
- `SessionState.conversation.last_clarification_kind` tracks whether the
  assistant is waiting on a core slot, a search type, or a refinement
  preference.
- `SessionState.conversation.last_search_outcome` tracks whether the last real
  search produced results, empty results, or no new results.
- `SessionState.conversation.last_recommendation_item_type` and
  `last_recommendation_query` preserve recommender carry-forward semantics
  across follow-up turns and pending recommendation clarifications.
- `SessionState.conversation.last_recommendation_result_ids` preserves the last
  grounded item ids shown to the user so follow-up turns can prefer unseen
  results and explicitly say when only duplicates remain.
- Deterministic clarification keeps asking for the same missing slot until that
  slot is captured, instead of skipping ahead.
- Generic trip-building turns can promote the session into recommendation setup
  even if the user never explicitly says `recommend hotels` or `recommend flights`.
- Vague replies like `Anything works` are resolved against the current
  clarification branch: they can choose a default search type, or, after a real
  empty search, trigger a stronger no-results explanation instead of a loop.
- Long recent transcript lines are flattened and truncated before planner
  replay so recommendation list copy does not dominate local-model prompt time.
- If the chat agent returns another clarification after the final required slot
  arrives, runtime executes the deterministic recommendation path immediately.
- `OrchestratorService` only trusts validated recommendation payloads for
  recommendation data and destination-specific claims.
- Raw LangChain message payloads are normalized behind an internal typed agent
  result adapter before orchestrator code inspects final AI messages, tool
  calls, or tool artifacts.
- Provider-backed chat still uses backend-owned grounded response composition
  after tool/state normalization; raw agent transcript text is not the final UX.
- Direct recommendation mode bypasses conversational composition and returns only
  schema-validated tool output.

## Fallback response requirements

- Planner execution failure, missing planner output, invalid planner JSON, or
  invalid planner state patch:
  - Use deterministic extraction plus deterministic guardrail planning.
- Chat-agent execution failure:
  - Use the validated planner-or-deterministic state plus deterministic
    guardrail planning.
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
