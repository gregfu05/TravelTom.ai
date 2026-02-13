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
- Strict input/output schemas.
- Persistent session state.

## Step 10 implementation snapshot

- Runtime modules:
  - `apps/api/app/services/orchestrator/policies.py`
  - `apps/api/app/services/orchestrator/service.py`
- Deterministic policy gates:
  - keyword intent classification (`recommend`, `refine`, `clarify`)
  - continuation logic for active sessions (`refine|itinerary|booking`)
- Tool execution:
  - recommendation tool call with schema-validated `RecommendationQuery`
  - configurable timeout policy (default 4s)
  - strict validation of `RecommendationToolResponse`
- Placeholder mode:
  - recommendation tool may return empty `results` while recommender integration is pending
  - orchestrator must ask for tighter constraints instead of fabricating options

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

