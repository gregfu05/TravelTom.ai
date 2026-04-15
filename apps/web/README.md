# Web App

Purpose: React frontend for TravelTom marketing pages, auth flows, and the planner chat workspace.

Ownership: Frontend.

## Stack

- React 19
- TypeScript
- Vite
- React Query
- Zod
- Zustand
- Vitest + Playwright

## Current Scope

- Public landing and informational routes
- Planner chat workspace backed by `/api/v1/chat`
- Recommendation rail and planner-specific UI state
- Login and signup screens for local auth
- Typed `/api/v1` client integration

Current route surface:

- `/`
- `/planner`
- `/why-traveltom`
- `/how-it-works`
- `/login`
- `/signup`

## Source Layout

- `src/app/`: route composition
- `src/pages/`: route-level screens
- `src/features/`: planner feature modules
- `src/components/`: reusable UI pieces
- `src/api/`: client and error handling
- `src/styles/`: tokens and page styling

## Common Commands

```bash
npm install
npm run dev
npm run build
npm run preview
npm run test
npm run test:e2e
npm run typecheck
```

## API Target

- Dev requests use `/api/v1/*` and are proxied by Vite.
- Configure proxy target in `apps/web/.env`:
  - `VITE_API_PROXY_TARGET=http://localhost:8000`
- Copy from `apps/web/.env.example` and set the backend port you actually run.

## Troubleshooting

- If `/api/v1/chat`, login, or signup fail with a `422 validation_error` and the backend says the request body is a string:
  1. Confirm the request payload is a JSON object, not a quoted JSON string.
  2. Keep JSON calls on the shared API client path so serialization happens once.
- If chat replies appear but recommendation cards do not:
  1. Confirm `/api/v1/chat` returns a non-empty `recommendations` array.
  2. Confirm `VITE_API_PROXY_TARGET` points to the running backend.
  3. Restart the backend after API wiring changes if dependencies were cached.

## Related Docs

- `src/README.md`
- `../../instructions/05-frontend/`
- `../api/README.md`
