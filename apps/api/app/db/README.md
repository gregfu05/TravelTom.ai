# Database Layer

Purpose: persistence wiring for the API runtime.

Ownership: Backend.

## What Lives Here

- `models/`: SQLAlchemy ORM models for chats, users, recommendations, events, and auth sessions.
- `session.py`: database session construction.
- `base.py`: shared declarative base import point.

## Notes

- Alembic migrations live outside this package under `apps/api/migrations/`.
- Keep ORM model definitions here and move request/response contracts to `../schemas/`.
- Coordinate schema changes with migrations and matching docs updates.

## Related Docs

- `../README.md`
- `../../../../instructions/02-backend/data-model.md`
- `../../../../instructions/02-backend/migrations.md`
