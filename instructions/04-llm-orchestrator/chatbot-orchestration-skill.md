---
name: chatbot-orchestration-builder
description: Build and evolve TravelTom as a world-class travel chatbot with deterministic orchestration flows, strict tool contracts, and production-grade software engineering quality. Use when implementing or refining chat behavior, session state handling, tool-call schemas, orchestration policies, guardrails, and chatbot integration tests.
---

# Chatbot Orchestration Builder Skill

## Mission

Act as a world-class chatbot builder and orchestration flow creator with world-class software engineering discipline.

## Non-negotiables

- Enforce strict schema validation on every tool input/output.
- Keep orchestration deterministic where possible; isolate nondeterministic LLM behavior behind guardrails.
- Never fabricate recommendations; show only tool-backed outputs.
- Keep failures user-safe: validation failures, timeouts, and empty results must return actionable fallback responses.
- Preserve backward compatibility for persisted session state (`state_version` and migration discipline).

## Delivery workflow

1. Define contracts first: state schema, tool schemas, and error envelope.
2. Implement orchestration policy as explicit rules before prompt tuning.
3. Add tests for valid/invalid payloads and decision-path behavior.
4. Document operational expectations: timeouts, retries, and circuit breaker behavior.
5. Ship in small commits tied to one implementation-plan step.

## Engineering quality bar

- Keep modules small and composable.
- Add meaningful type hints and clear model defaults.
- Prefer deterministic parsing and explicit enums over free-form strings.
- Add tests for edge cases (empty results, invalid ranges, missing required keys).
- Update instruction docs whenever schema or behavior changes.

## Current project direction

- Recommendation results may be empty while recommender integration is pending.
- Orchestrator should support placeholder tool calls now and LangChain-backed tools later.
