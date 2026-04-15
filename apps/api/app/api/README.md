# API Layer

Purpose: HTTP-facing routers and API version composition.

Ownership: Backend.

## What Lives Here

- `v1/`: versioned route modules for health, auth, chat, and recommendations.
- `__init__.py`: router aggregation imported by `app.main`.

## Design Notes

- Keep this layer focused on HTTP mapping, dependency wiring, and response codes.
- Shared request and response models belong in `../schemas/`, not inline in route files.
- Route behavior should delegate into services rather than duplicate business logic.

## Important Entrypoints

- `v1/chat.py`
- `v1/recommendations.py`
- `v1/auth.py`
- `v1/health.py`

## Related Docs

- `../README.md`
- `../../../../instructions/02-backend/api-design.md`
