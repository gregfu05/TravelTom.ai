# Auth Flow

Purpose: frontend helpers for login and signup interaction flows.

Ownership: Frontend.

## What Lives Here

- `authFlow.ts`: client-side auth request and flow helpers.

## Notes

- Coordinate changes here with backend auth routes under `apps/api/app/api/v1/auth.py`.
- Keep auth-specific UI state in the auth or page layer instead of general shared components.

## Related Docs

- `../README.md`
- `../../../../apps/api/README.md`
