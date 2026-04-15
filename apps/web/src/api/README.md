# Web API Client

Purpose: frontend HTTP integration and client-side API error normalization.

Ownership: Frontend.

## What Lives Here

- `client.ts`: shared request path for `/api/v1/*`.
- `errorHandling.ts`: normalization of backend error responses for UI use.

## Notes

- Keep JSON request serialization centralized here to avoid double-encoding bugs.
- If backend contracts change, update this area together with the matching route tests.

## Related Docs

- `../README.md`
- `../../../../instructions/05-frontend/frontend-architecture.md`
