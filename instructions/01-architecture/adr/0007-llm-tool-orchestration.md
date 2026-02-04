# ADR: Tool-first LLM orchestration with strict schemas

- Status: Accepted
- Date: 2026-02-04

## Context

The LLM must orchestrate without inventing recommendations. Tool calls must be validated and deterministic.

## Decision

Use a tool-first orchestration strategy. The LLM can only call registered tools with explicit Pydantic schemas. Tool outputs are validated, and any validation failure results in a fallback response or retry.

## Alternatives considered

- Free-form LLM responses: High risk of hallucinated recommendations.
- Few-shot guidance only: Insufficient guardrails.

## Consequences

- Positive: Enforced determinism and safety.
- Negative: Additional schema maintenance.
- Risks: Schema drift between tool and orchestrator; mitigate with shared models and contract tests.

## Notes

See `04-llm-orchestrator/tool-schemas.md`.

