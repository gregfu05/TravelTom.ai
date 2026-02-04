# ADR: URL-based API versioning

- Status: Accepted
- Date: 2026-02-04

## Context

We need stable, evolvable API contracts for frontend and orchestrator interactions.

## Decision

Use URL-based versioning with a `/api/v1` prefix. Within a version, changes must be backward compatible; breaking changes require `/api/v2`.

## Alternatives considered

- Header-based versioning: Harder to debug and discover.
- Query param versioning: Less conventional for REST-style APIs.

## Consequences

- Positive: Clear routing and documentation. Works well with OpenAPI.
- Negative: Versioning adds some duplication.
- Risks: Version sprawl if not managed; mitigate with clear deprecation policy.

## Notes

See `02-backend/api-design.md`.

