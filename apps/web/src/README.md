# Web Source

Purpose: client-side source for the TravelTom React application.

Ownership: Frontend.

## What Lives Here

- `app/`: route composition and app shell wiring.
- `api/`: typed HTTP client and error handling.
- `auth/`: login/signup flow helpers.
- `components/`: reusable UI building blocks.
- `features/`: feature-scoped planner UI and state logic.
- `pages/`: route-level page components.
- `styles/`: design tokens and page-specific CSS.
- `test/`: frontend test helpers and setup.

## Current Runtime Shape

The app currently serves the marketing/entry routes plus the planner workspace:

- `/`
- `/planner`
- `/why-traveltom`
- `/how-it-works`
- `/login`
- `/signup`

## Related Docs

- `../README.md`
- `../../../instructions/05-frontend/frontend-architecture.md`
- `../../../instructions/05-frontend/ux-flows.md`
