# Repository Layer

Purpose: feature-scoped data access boundaries used by API services.

Ownership: Backend.

## What Lives Here

- `chat.py`: chat/session/message/recommendation persistence helpers.
- `users.py`: user-related persistence.
- `auth_sessions.py`: persisted local auth session lifecycle.

## Design Notes

- Repositories should stay close to storage concerns.
- Cross-entity workflows belong in services or unit-of-work helpers, not in route files.
- Keep repository APIs explicit so tests can target business logic without HTTP setup.

## Related Docs

- `../README.md`
- `../../../../instructions/02-backend/services-and-modules.md`
