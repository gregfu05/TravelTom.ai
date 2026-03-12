# Orchestrator Overview

## Responsibilities

- Run `/api/v1/chat` through a real LangChain `create_agent` loop.
- Supply LangChain `@tool` recommendation tools from the shared backend service layer.
- Keep recommendation retrieval tool-first and deterministic.
- Normalize agent transcripts into grounded assistant responses and validated tool-backed recommendations.
- Persist schema-valid state and recommendation snapshots via `/api/v1/chat`.

## Hard constraints

- The LLM must not invent recommendations.
- Recommendation items are only returned from `RecommendationToolResponse`.
- `SessionState`, `RecommendationQuery`, and `RecommendationToolResponse` remain strict Pydantic contracts.

## Runtime modules

- `apps/api/app/services/travel_tom_agent.py`
  - Shared route-facing `TravelTomAgent` entrypoint for backend agent behavior.
  - Owns LangChain-native `create_agent` construction for chat and direct recommendation paths.
  - Registers the recommendation tool with LangChain's `@tool` decorator.
  - Exposes `handle_chat` and `handle_recommendation_query` for `/chat` and
    `/recommendations/query`.
- `apps/api/app/services/orchestrator/service.py`
  - Normalizes LangChain agent transcripts into `OrchestratorResponse`.
  - Builds per-request state context, deterministic fallback queries, and
    tool/error handling.
  - Keeps deterministic extraction, query shaping, and safe fallback copy.
- `apps/api/app/services/orchestrator/policies.py`
  - Shared guardrails and deterministic fallback copy helpers.
- `apps/api/app/services/orchestrator/extraction.py`
  - Deterministic guardrail extraction from raw user text.
- `apps/api/app/services/orchestrator/llm_provider.py`
  - Builds LangChain-native OpenAI and Ollama chat models.
  - Provides deterministic in-process models for disabled chat mode and direct
    recommendation mode.

## Chat agent flow

1. `/api/v1/chat` resolves the shared `TravelTomAgent` and calls `handle_chat`.
2. `OrchestratorService` applies deterministic state extraction and builds a hidden
   runtime context message from the validated `SessionState`.
3. The shared chat agent, created with LangChain `create_agent`, receives:
   - one chat model (`ChatOpenAI`, `ChatOllama`, or the deterministic disabled model)
   - one `@tool` recommendation tool
   - a bounded system prompt that allows only clarification or grounded tool use
4. If the agent calls `recommendation_query`, the tool validates the request,
   executes the recommender, validates `RecommendationToolResponse`, and returns a
   runtime artifact describing success or failure.
5. `OrchestratorService` reads the final agent transcript, ignores any invented
   recommendation content, and emits `OrchestratorResponse` using only validated
   tool artifacts plus deterministic fallback copy when needed.

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
- Tool timeout, invalid payload, and unexpected tool failures return explicit safe fallback messages.
- Empty tool results are explicit and return a constraints-tightening message path.
- Router contract and persistence behavior in `/api/v1/chat` are unchanged.
- `/api/v1/recommendations/query` remains deterministic and does not depend on
  conversational planning state.

## Failure handling

- Chat-model or agent execution failure:
  - Fall back to deterministic extraction plus direct deterministic tool execution
    when the guardrail policy says a search should still run.
- Tool timeout:
  - Return retry-safe deterministic message.
- Invalid tool output:
  - Return deterministic invalid-payload fallback message.
- Empty tool results:
  - Return deterministic no-strong-match guidance, even if the agent's final
    message is blank or unsafe to trust.
- Invalid tool-call arguments:
  - Treat as an invalid request and ask for the missing trip details instead of guessing.
