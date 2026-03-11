# Orchestrator Overview

## Responsibilities

- Interpret user intent with an LLM planner.
- Merge structured planner state updates into persisted `SessionState`.
- Keep recommendation retrieval tool-first and deterministic.
- Compose grounded assistant responses from validated state and tool outputs.
- Persist schema-valid state and recommendation snapshots via `/api/v1/chat`.

## Hard constraints

- The LLM must not invent recommendations.
- Recommendation items are only returned from `RecommendationToolResponse`.
- `SessionState`, `RecommendationQuery`, and `RecommendationToolResponse` remain strict Pydantic contracts.

## Runtime modules

- `apps/api/app/services/orchestrator/service.py`
  - LLM-first orchestration path in `OrchestratorService.handle_message`.
  - Structured planner and response-composer chains.
  - Unified response-composition entry point for clarification, invalid-request,
    results, and empty-results outcomes.
  - Deterministic recommendation tool execution with timeout and schema validation.
- `apps/api/app/services/orchestrator/policies.py`
  - Prompt-context builders and TravelTom conversational persona guidance.
  - Deterministic fallback planner and branded safe-fallback copy helpers.
- `apps/api/app/services/orchestrator/extraction.py`
  - Deterministic guardrail extraction from raw user text.
  - Structured state-patch merge helper for LLM planner output.
- `apps/api/app/services/orchestrator/langchain_compat.py`
  - LangChain compatibility shims and structured-payload normalization.

## LLM-first orchestration flow

1. Build planner prompt context from current `SessionState` + latest user message.
2. Invoke planner model and validate output as `LLMOrchestrationPlan`.
3. Apply validated `state_patch` to `SessionState`, then run deterministic extraction guardrails.
4. If planner says clarify, return planner clarification message (or deterministic fallback copy).
5. If planner says recommend/refine, map `query_controls` to `RecommendationQuery` and execute recommendation tool.
6. Validate tool output as `RecommendationToolResponse`.
7. Build response prompt context from validated state + tool results and invoke response composer for normal user-facing reply paths (`clarification`, `invalid_request`, `results`, `empty_results`).
8. If response-composer output is invalid/unavailable, use deterministic fallback copy written in the same TravelTom persona.

## Deterministic guarantees

- Ranking behavior and `ranking_version` (`heuristic-v1`) are unchanged.
- Recommendation grounding is unchanged: the composer may only mention items present in validated tool output.
- Tool timeout, invalid payload, and unexpected tool failures return explicit safe fallback messages.
- Empty tool results are explicit and return a constraints-tightening message path.
- Router contract and persistence behavior in `/api/v1/chat` are unchanged.

## Failure handling

- Planner failure or invalid planner payload:
  - Fall back to deterministic guardrail planner.
- Invalid structured state patch:
  - Ignore patch and continue with prior state + deterministic extraction guardrails.
- Tool timeout:
  - Return retry-safe deterministic message.
- Invalid tool output:
  - Return deterministic invalid-payload fallback message.
- Empty tool results:
  - Route through response composition when available, with deterministic no-strong-match fallback if composition fails.
- Invalid request after query-schema mapping:
  - Route through response composition when available, with deterministic request-for-missing-details fallback if composition fails.
- Response composer failure/invalid payload:
  - Return deterministic fallback response text in the same TravelTom persona.
