# Orchestrator Overview

## Responsibilities

- Run `/api/v1/chat` through a LangChain `create_agent` conversational loop.
- Supply LangChain `@tool` recommendation tools from the shared backend service layer.
- Reuse bounded persisted conversation history plus validated `SessionState` on every turn.
- Keep recommendation retrieval tool-first and deterministic.
- Apply deterministic extraction and carry-forward shaping before agent invocation.
- Normalize agent transcripts into grounded assistant responses backed only by validated tool output.
- Persist schema-valid state and recommendation snapshots via `/api/v1/chat`.

## Hard constraints

- The LLM must not invent recommendations.
- Recommendation items are only returned from `RecommendationToolResponse`.
- `SessionState`, `RecommendationQuery`, and `RecommendationToolResponse` remain strict Pydantic contracts.

## Runtime modules

- `apps/api/app/services/travel_tom_agent.py`
  - Shared route-facing `TravelTomAgent` entrypoint for backend agent behavior.
  - Owns the shared chat `create_agent` instance and the deterministic direct
    recommendation `create_agent` instance.
  - Registers the recommendation tool with LangChain's `@tool` decorator.
  - Exposes `handle_chat` and `handle_recommendation_query` for `/chat` and
    `/recommendations/query`.
- `apps/api/app/services/orchestrator/service.py`
  - Runs deterministic pre-extraction before the chat agent sees the turn.
  - Builds hidden runtime context from validated state, bounded recent
    transcript, and deterministic carry-forward query hints.
  - Normalizes agent transcripts into schema-valid API responses.
  - Keeps deterministic fallback query shaping, clarification continuity, and
    tool/error handling.
- `apps/api/app/services/orchestrator/policies.py`
  - Shared deterministic clarification and fallback helpers.
- `apps/api/app/services/orchestrator/extraction.py`
  - Deterministic guardrail extraction from raw user text.
  - Resolves carry-forward item type and effective recommender query text for
    underspecified follow-up turns.
- `apps/api/app/services/orchestrator/llm_provider.py`
  - Builds OpenAI and Ollama chat models used by the chat agent.
  - Provides deterministic in-process models for disabled chat mode fallback
    and direct recommendation mode.

## Chat orchestration flow

1. `/api/v1/chat` resolves the shared `TravelTomAgent` and calls `handle_chat`.
2. The route loads a bounded recent transcript window from persisted `messages`
   and hydrates the validated `SessionState` from `sessions.state_json`.
3. `OrchestratorService` applies deterministic extraction to the latest user turn
   before the chat agent runs.
4. Runtime builds hidden agent context from:
   - validated current state
   - bounded recent transcript replay
   - deterministic carry-forward query hints for follow-up turns
5. The chat `create_agent` loop either:
   - asks a clarification question, or
   - calls `recommendation_query`
6. `recommendation_query` validates the request, executes the recommender,
   validates `RecommendationToolResponse`, and returns deterministic runtime data.
7. `OrchestratorService` normalizes the final agent transcript into
   `OrchestratorResponse`, updates remembered recommendation intent fields in
   `SessionState.conversation`, and ignores model-invented recommendation content.
8. If the agent path fails, runtime falls back to deterministic clarification or
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
- Deterministic extraction still runs before planner state merging.
- Deterministic extraction still runs before agent invocation.
- Follow-up turns can reuse `conversation.last_recommendation_item_type` and
  `conversation.last_recommendation_query` when the user says things like
  `show me more`, `another option`, or `cheaper`.
- Clarification fallback is progressive and slot-aware, using
  `state.conversation.last_requested_slots` plus current missing constraints.
- Tool timeout, invalid payload, and unexpected tool failures return explicit safe fallback messages.
- Empty tool results are explicit and return a constraints-tightening message path.
- Router contract and persistence behavior in `/api/v1/chat` are unchanged.
- `/api/v1/recommendations/query` remains deterministic and does not depend on
  conversational planning state.

## Failure handling

- Chat-agent execution failure:
  - Fall back to deterministic extraction plus deterministic guardrail routing.
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
