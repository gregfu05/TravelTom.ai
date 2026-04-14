# Orchestrator Overview

## Responsibilities

- Run `/api/v1/chat` through a schema-validated planner step plus a LangChain
  `create_agent` conversational loop.
- Supply LangChain `@tool` recommendation tools from the shared backend service layer.
- Reuse bounded persisted conversation history plus validated `SessionState` on every turn.
- Keep recommendation retrieval tool-first and deterministic.
- Apply deterministic extraction and carry-forward shaping as planner hints and
  deterministic fallbacks before agent invocation.
- Use the structured planner as the default extraction and routing layer for
  normal non-empty `/chat` turns when a planner provider is available.
- Keep planner prompt replay bounded by flattening and truncating recent
  transcript lines before provider-backed planning.
- Normalize agent transcripts into grounded assistant responses backed only by validated tool output.
- Persist schema-valid state and recommendation snapshots via `/api/v1/chat`.

## Hard constraints

- The LLM must not invent recommendations.
- Recommendation items are only returned from `RecommendationToolResponse`.
- `SessionState`, `RecommendationQuery`, and `RecommendationToolResponse` remain strict Pydantic contracts.

## Runtime modules

- `apps/api/app/services/travel_tom_agent.py`
  - Shared route-facing `TravelTomAgent` entrypoint for backend agent behavior.
  - Owns the provider-backed structured planner client used before chat-agent
    execution.
  - Owns the shared chat `create_agent` instance and the deterministic direct
    recommendation `create_agent` instance.
  - Registers the recommendation tool with LangChain's `@tool` decorator.
  - Stays adapter-focused: planner invocation, LangChain agent execution, and
    recommendation tool execution live here, while orchestration policy and
    response/state decisions live under `services/orchestrator/`.
  - Exposes `handle_chat` and `handle_recommendation_query` for `/chat` and
    `/recommendations/query`.
- `apps/api/app/services/orchestrator/service.py`
  - Coordinates the phased runtime rather than owning every branch directly.
  - Builds hidden runtime context from validated state, bounded recent
    transcript, and validated recommendation query controls.
  - Maps normalized phase output into schema-valid `OrchestratorResponse`
    payloads and preserves clarification continuity / intent memory.
- `apps/api/app/services/orchestrator/turn_preparer.py`
  - Owns deterministic hint extraction, planner invocation/validation,
    planner cooldown handling, plan normalization, and recommendation slot
    gating before routing.
- `apps/api/app/services/orchestrator/decision_engine.py`
  - Owns the routing decision between direct runtime handling and chat-agent
    invocation once a turn has been prepared.
- `apps/api/app/services/orchestrator/recommendation_runner.py`
  - Owns validated recommendation query construction and deterministic
    recommendation execution for fallback and bypass paths.
- `apps/api/app/services/orchestrator/response_assembler.py`
  - Owns normalized recommendation outcome handling for results, empty
    results, duplicate-only follow-ups, and grounded fallback result copy.
- `apps/api/app/services/orchestrator/runtime_types.py`
  - Defines internal typed handoff objects between preparation, routing,
    recommendation execution, and transcript normalization phases.
- `apps/api/app/services/orchestrator/policies.py`
  - Shared planner prompt builder plus deterministic clarification and fallback
  helpers.
  - Flattens and truncates recent transcript replay for planning and response
    composition so grounded recommendation lists do not bloat later prompts.
  - Owns deterministic meta-question, repair-turn, and duplicate-only
    follow-up messaging.
- `apps/api/app/services/orchestrator/extraction.py`
  - Deterministic guardrail extraction from raw user text.
  - Applies schema-validated planner `state_patch` payloads through
    `apply_structured_state_patch(...)`.
  - Resolves carry-forward item type and effective recommender query text for
    underspecified follow-up turns.
  - Uses token-aware and negation-aware interest extraction so `Santa Barbara`
    does not imply `bar`, and repair turns like `not restaurants` do not add
    positive restaurant interest.
- `apps/api/app/services/orchestrator/llm_provider.py`
  - Builds OpenAI and Ollama chat models used by the chat agent.
  - Provides deterministic in-process models for disabled chat mode fallback
    and direct recommendation mode.

## Chat orchestration flow

1. `/api/v1/chat` resolves the shared `TravelTomAgent` and calls `handle_chat`.
2. The route loads a bounded recent transcript window from persisted `messages`
   and hydrates the validated `SessionState` from `sessions.state_json`.
3. `TurnPreparer` applies deterministic extraction to the latest user turn as
   advisory hint state.
4. A structured planner receives:
   - validated current state
   - bounded recent transcript replay
   - raw user text
   - deterministic extraction and carry-forward hints
   - on normal non-empty `/chat` turns whenever planner support is available
5. On Ollama, structured planning prefers the OpenAI-compatible endpoint with a
   JSON-schema response contract and a larger planner timeout budget than the
   chat-agent path, so multi-turn planner prompts do not silently degrade to
   deterministic fallback on local runtimes.
6. The planner output is validated against `LLMOrchestrationPlan`, its
   `state_patch` is merged through `apply_structured_state_patch(...)`, and
   deterministic guardrails keep tool routing safe.
7. `RecommendationDecisionEngine` decides whether runtime can answer directly
   or still needs the chat-agent loop.
8. Runtime builds hidden agent context from:
   - merged validated state
   - bounded recent transcript replay
   - validated recommendation query controls and carry-forward hints
9. If the planner returned a clarification path, runtime can send that
   clarification directly after validation without requiring a second model hop.
10. On search-ready turns that still need agent execution, the chat
   `create_agent` loop either:
   - asks a clarification question, or
   - calls `recommendation_query`
   - or is bypassed on high-confidence search-ready reply turns when runtime can
     execute the same grounded recommendation path deterministically
11. `recommendation_query` validates the request, executes the recommender,
   validates `RecommendationToolResponse`, and returns deterministic runtime data.
12. `RecommendationRunner` and `ResponseAssembler` normalize both agent-backed
   tool results and deterministic fallback execution through the same
   recommendation outcome path.
13. `OrchestratorService` normalizes the final agent transcript into
   `OrchestratorResponse`, updates remembered recommendation intent fields in
   `SessionState.conversation`, preserves pending query/item-type memory across
   clarification turns, tracks surfaced recommendation ids for duplicate
   suppression, tracks whether the assistant is waiting on a core slot, search
   type, or refinement preference, and ignores model-invented recommendation
   content.
14. If planner output is missing, invalid, or unsafe, runtime falls back to
    deterministic extraction plus deterministic guardrail planning.
15. If the agent path fails or skips a recommendation call after the final
   required slot arrives, runtime falls back to deterministic clarification or
   deterministic recommendation execution using the same carry-forward shaping.

## Direct recommendation flow

1. `/api/v1/recommendations/query` resolves the same shared `TravelTomAgent`.
2. The route calls `handle_recommendation_query`.
3. A separate deterministic `create_agent` instance forces a single
   `recommendation_query` tool call from the serialized request payload.
4. The route returns the validated `RecommendationResponse` extracted from the
   tool artifact without model-authored recommendation text or session mutation.

## Deterministic guarantees

- Ranking behavior and `ranking_version` (`heuristic-v1`) are unchanged.
- Recommendation grounding is unchanged: assistant copy may only mention items
  present in validated tool output.
- Structured planner output is primary for persisted state on normal `/chat`
  turns, but state mutation still requires schema validation.
- Deterministic extraction still runs before planner state merging and remains a
  hint generator plus fallback path.
- Deterministic fallback is defensive rather than authoritative: weak phrases
  like `be honest`, `lower cost`, or other filler text must not overwrite an
  already valid destination.
- Destination slot capture is conservative: assignment-style phrases like
  `destination is Lisbon` and concise bare replies like `Lisbon` still work,
  but greetings and meta turns like `Hello Tommy` or `what do you mean` do not
  persist `constraints.destination`.
- Planner-authored `query_controls` can shape effective item type and query
  text, but deterministic guardrails still veto unsafe hotel searches
  that are missing required trip details.
- Hotel searches wait for destination, dates, and budget, while restaurant and
  activity searches require destination.
- Follow-up turns can reuse `conversation.last_recommendation_item_type` and
  `conversation.last_recommendation_query` when the user says things like
  `show me more`, `another option`, `cheaper`, or `lower cost`.
- Generic trip-building flows can collect destination, dates, and budget first,
  then ask a deterministic search-type question (`hotels`, `restaurants`, or
  `activities`) before a search runs.
- Vague replies to that search-type question keep clarification active until
  the user chooses one of the supported item types explicitly.
- Follow-up turns also remember recently surfaced recommendation ids so
  duplicate-only tool responses can ask for refinement instead of replaying the
  same list as if it were new.
- Clarification turns also preserve pending recommendation intent, item type,
  and carried query text so users do not need to restate `recommend`.
- Clarification fallback is progressive and slot-aware, using
  `state.conversation.last_requested_slots` plus current missing constraints,
  and it keeps re-asking the same slot until that slot is actually captured.
- When planner-backed state cleanly satisfies a pending slot or search-type
  clarification and the search is already safe, runtime may execute the
  deterministic recommendation path immediately instead of waiting on the chat
  agent to restate the same tool call.
- Tool timeout, invalid payload, and unexpected tool failures return explicit safe fallback messages.
- Empty tool results are explicit and return a constraints-tightening message path.
- Repeated vague replies after real empty-result or duplicate-only searches
  return stronger no-results guidance instead of re-running the same empty
  search or looping on the same optimization prompt.
- Router contract and persistence behavior in `/api/v1/chat` are unchanged.
- `/api/v1/recommendations/query` remains deterministic and does not depend on
  conversational planning state.

## Failure handling

- Planner failure, invalid planner JSON, or invalid planner state patch:
  - Fall back to deterministic extraction plus deterministic guardrail planning.
- Chat-agent execution failure:
  - Fall back to the validated planner-or-deterministic state plus deterministic
    guardrail routing.
  - If the fallback path still permits a search, execute the deterministic
    recommendation path and use deterministic grounded copy.
- Tool timeout:
  - Return retry-safe deterministic message.
- Invalid tool output:
  - Return deterministic invalid-payload fallback message.
- Empty tool results:
  - Return deterministic no-strong-match guidance and ask for a tighter next detail.
- Invalid tool-call arguments or incomplete constraints:
  - Ask for the next most useful missing trip detail instead of guessing.
