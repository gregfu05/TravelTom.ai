# Orchestrator Overview

## Responsibilities

- Run `/api/v1/chat` through a planner/composer orchestration loop.
- Supply LangChain `@tool` recommendation tools from the shared backend service layer.
- Reuse bounded persisted conversation history plus validated `SessionState` on every turn.
- Keep recommendation retrieval tool-first and deterministic.
- Merge deterministic extraction and planner-proposed state patches into canonical validated state.
- Compose grounded assistant responses from validated tool-backed recommendations only.
- Persist schema-valid state and recommendation snapshots via `/api/v1/chat`.

## Hard constraints

- The LLM must not invent recommendations.
- Recommendation items are only returned from `RecommendationToolResponse`.
- `SessionState`, `RecommendationQuery`, and `RecommendationToolResponse` remain strict Pydantic contracts.

## Runtime modules

- `apps/api/app/services/travel_tom_agent.py`
  - Shared route-facing `TravelTomAgent` entrypoint for backend agent behavior.
  - Owns LLM-backed planner/composer invocation for chat and LangChain
    `create_agent` construction for direct recommendation mode.
  - Registers the recommendation tool with LangChain's `@tool` decorator.
  - Exposes `handle_chat` and `handle_recommendation_query` for `/chat` and
    `/recommendations/query`.
- `apps/api/app/services/orchestrator/service.py`
  - Runs turn orchestration in four steps:
    - deterministic extraction
    - structured planning
    - optional deterministic recommendation execution
    - grounded response composition
  - Merges validated planner state patches into canonical `SessionState`.
  - Keeps deterministic query shaping, clarification fallback logic, and
    tool/error handling.
- `apps/api/app/services/orchestrator/policies.py`
  - Shared planner/composer prompt builders, guardrails, and deterministic
    fallback copy helpers.
- `apps/api/app/services/orchestrator/extraction.py`
  - Deterministic guardrail extraction from raw user text.
- `apps/api/app/services/orchestrator/llm_provider.py`
  - Builds OpenAI and Ollama chat models used by planner/composer calls.
  - Provides deterministic in-process models for disabled chat mode fallback
    and direct recommendation mode.

## Chat orchestration flow

1. `/api/v1/chat` resolves the shared `TravelTomAgent` and calls `handle_chat`.
2. The route loads a bounded recent transcript window from persisted `messages`
   and hydrates the validated `SessionState` from `sessions.state_json`.
3. `OrchestratorService` applies deterministic extraction to the latest user turn
   before any LLM planning.
4. The planner receives:
   - validated current state
   - bounded recent transcript
   - latest user message
   - a hard `max_results` bound for this turn
5. The planner returns JSON with:
   - `intent`
   - `should_call_recommendation_tool`
   - optional `clarification_message`
   - `state_patch`
   - `query_controls`
6. Runtime merges the planner patch into state with strict validation. Invalid
   patches are ignored and orchestration continues from the deterministic state.
7. If a search is appropriate, `recommendation_query` validates the request,
   executes the recommender, validates `RecommendationToolResponse`, and returns
   deterministic runtime data.
8. The composer receives:
   - validated state
   - bounded recent transcript
   - latest user message
   - validated recommendation results only
   - a deterministic fallback message
9. `OrchestratorService` emits `OrchestratorResponse` with schema-valid state,
   grounded recommendations, and safe fallback copy when planning/composition
   fails.

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
- Deterministic extraction still runs before planner state merging.
- Clarification fallback is progressive and slot-aware, using
  `state.conversation.last_requested_slots` plus current missing constraints.
- Tool timeout, invalid payload, and unexpected tool failures return explicit safe fallback messages.
- Empty tool results are explicit and return a constraints-tightening message path.
- Router contract and persistence behavior in `/api/v1/chat` are unchanged.
- `/api/v1/recommendations/query` remains deterministic and does not depend on
  conversational planning state.

## Failure handling

- Planner or composer execution failure:
  - Fall back to deterministic extraction plus deterministic guardrail planning.
  - If the fallback plan still permits a search, execute the deterministic
    recommendation path and use deterministic grounded copy.
- Tool timeout:
  - Return retry-safe deterministic message.
- Invalid tool output:
  - Return deterministic invalid-payload fallback message.
- Empty tool results:
  - Return deterministic no-strong-match guidance and ask for a tighter next detail.
- Invalid tool-call arguments or incomplete constraints:
  - Ask for the next most useful missing trip detail instead of guessing.
