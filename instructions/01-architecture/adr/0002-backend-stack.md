# ADR: Backend stack with FastAPI + Pydantic + SQLAlchemy + Alembic

- Status: Accepted
- Date: 2026-02-04

## Context

The backend must expose APIs, orchestrate LLM calls, and run a deterministic recommender. It needs strong schema validation and a mature ORM/migrations workflow.

## Decision

Use FastAPI with Pydantic v2 for API schemas and validation, SQLAlchemy 2.x for ORM, and Alembic for migrations.

## Alternatives considered

- Django: Too opinionated for service-style APIs and fine-grained module boundaries.
- Flask: Lacks built-in validation and async support.
- Prisma or SQLModel: Less flexible with complex schemas and migrations.

## Consequences

- Positive: Strong typing, fast iteration, built-in OpenAPI, reliable migrations.
- Negative: Requires explicit dependency injection patterns.
- Risks: Async + SQLAlchemy can be misused; mitigate with clear patterns in `02-backend/services-and-modules.md`.

## Notes

See `02-backend/api-design.md` and `02-backend/migrations.md`.

