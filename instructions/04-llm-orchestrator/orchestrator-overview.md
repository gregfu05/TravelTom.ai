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

