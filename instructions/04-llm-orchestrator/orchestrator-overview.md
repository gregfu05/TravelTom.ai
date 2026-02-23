# Orchestrator Overview

## Responsibilities

- Interpret user intent.
- Extract structured constraints and preferences.
- Decide next action (clarify vs recommend vs refine).
- Generate fluent responses grounded in tool outputs.

## Hard constraints

- The LLM must not invent recommendations.
- All recommendations come from explicit tool calls.
- Tool calls are validated with strict schemas.

## Orchestrator pattern

- Tool-first routing.
- Deterministic decision logic.
- LangChain runnable orchestration.
- Strict input/output schemas.
- Persistent session state.

## Step 10 implementation snapshot

- Runtime modules:
  - `apps/api/app/services/orchestrator/policies.py`
  - `apps/api/app/services/orchestrator/service.py`
  - `apps/api/app/services/orchestrator/extraction.py`
- Deterministic policy gates:
  - keyword intent classification (`recommend`, `refine`, `clarify`)
  - continuation logic for active sessions (`refine|itinerary|booking`)
- Deterministic state extraction:
  - parse origin/destination, date ranges, trip length, budget, and party size from user text
  - merge extracted values into persisted `SessionState` before policy routing and tool calls
  - persist extracted destinations into `entities.destinations`
  - extract request-level recommendation filters (for example `item_type=hotel|flight|destination`) from user text
- Tool execution:
  - LangChain `StructuredTool` for recommendation calls with schema-validated `RecommendationQuery`
  - LangChain `RunnableLambda` chain for tool invocation and response parsing
  - configurable timeout policy (default 4s)
  - strict validation of `RecommendationToolResponse`
- Placeholder mode:
  - recommendation tool may return empty `results` while recommender integration is pending
  - orchestrator must ask for tighter constraints instead of fabricating options
- Compatibility mode:
  - if `langchain_core` is unavailable locally, a lightweight fallback shim keeps local tests runnable
  - production/runtime environments should install `langchain-core`

## Failure handling

- Validation error: log event and return a user-friendly error.
- Tool timeout: return a partial response with a retry prompt.
- Empty results: ask for more constraints.

## Reliability measures

- JSON schema validation.
- Fallback logic on extraction failure.
- Timeouts and circuit breakers.
- Booking claims only after adapter confirmation.

## Skill reference

- Builder skill: [chatbot-orchestration-skill.md](chatbot-orchestration-skill.md)

