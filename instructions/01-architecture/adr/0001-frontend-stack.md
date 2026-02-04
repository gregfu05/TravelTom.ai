# ADR: Frontend stack with React + TypeScript + Vite

- Status: Accepted
- Date: 2026-02-04

## Context

We need a modern web frontend for chat and recommendation workflows. The stack must be fast to develop, easy to test, and strongly typed.

## Decision

Use React with TypeScript and Vite for the web frontend. Adopt a lightweight state manager (Zustand) for shared state and React Query for data fetching and caching.

## Alternatives considered

- Next.js: More infrastructure than needed for a demo; SSR not required.
- Vue/Svelte: Good options, but the team skill profile favors React.
- Redux Toolkit: Heavier boilerplate for this scope.

## Consequences

- Positive: Fast iteration, strong type safety, simple deployment.
- Negative: Requires client-side routing and API proxy configuration.
- Risks: Without guardrails, state can become scattered; mitigate by keeping state modules small and documented.

## Notes

- Optional UI library for acceleration: MUI or Chakra UI (per design doc).

See `05-frontend/frontend-architecture.md`.

