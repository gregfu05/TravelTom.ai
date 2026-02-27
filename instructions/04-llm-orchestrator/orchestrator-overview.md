# Orchestrator Overview

## Responsibilities

- Interpret user intent with an LLM planner.
- Merge structured planner state updates into persisted `SessionState`.
- Keep recommendation retrieval tool-first and deterministic.
- Compose grounded assistant responses from validated tool results.
- Persist schema-valid state and recommendation snapshots via `/api/v1/chat`.

## Hard constraints

- The LLM must not invent recommendations.
- Recommendation items are only returned from `RecommendationToolResponse`.
- `SessionState`, `RecommendationQuery`, and `RecommendationToolResponse` remain strict Pydantic contracts.

## Runtime modules

- `apps/api/app/services/orchestrator/service.py`
  - LLM-first orchestration path in `OrchestratorService.handle_message`.
  - Structured planner and response-composer chains.
  - Deterministic recommendation tool execution with timeout and schema validation.
- `apps/api/app/services/orchestrator/policies.py`
  - Structured planner/composer output models.
  - Prompt-context builders.
  - Deterministic fallback planner and clarification helpers.
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
7. Build response prompt context from validated tool results and invoke response composer.
8. If response-composer output is invalid/unavailable, use deterministic fallback copy.

## Deterministic guarantees

- Ranking behavior and `ranking_version` (`heuristic-v1`) are unchanged.
- Tool timeout, invalid payload, and unexpected tool failures return explicit safe fallback messages.
- Empty tool results are explicit and return a constraints-tightening message path.
- Router contract and persistence behavior in `/api/v1/chat` are unchanged.

## Failure handling

- Planner failure or invalid planner payload:
  - Fall back to deterministic guardrail planner.
- Invalid structured state patch:
  - Ignore patch and continue with prior state + deterministic extraction guardrails.
- Tool timeout:
  - Return retry-safe timeout message.
- Invalid tool output:
  - Return invalid-payload fallback message.
- Empty tool results:
  - Return explicit no-strong-match fallback and request tighter constraints.
- Response composer failure/invalid payload:
  - Return deterministic fallback response text grounded in tool outputs.
