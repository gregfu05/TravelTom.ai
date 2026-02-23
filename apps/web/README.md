# Web App

Purpose: React frontend for the TravelTom chat experience and planning UI.
Ownership: Frontend.

## Stack

- React + TypeScript + Vite
- React Query for server state
- Zustand (reserved for session UI state in upcoming steps)
- Zod for API response validation

## Current scope

- Frontend scaffold (MVP Step 14 foundation)
- Homepage with responsive, accessibility-aware layout and tokenized styling
- Planner route with chat UI and `/api/v1/chat` message flow
- Recommendations panel in planner that renders ranked results from the latest
  chat response
- Standalone informational routes:
  - `/planner`
  - `/why-traveltom`
  - `/how-it-works`
- Typed API client for `/api/v1` integration

## Troubleshooting

- If chat replies appear but recommendation cards do not:
  1. Confirm backend `/api/v1/chat` response includes a non-empty
     `recommendations` array in the browser network tab.
  2. Confirm API proxy target points to the running backend
     (`VITE_API_PROXY_TARGET`, default `http://localhost:8000`).
  3. Restart backend after API wiring changes so cached dependencies refresh.

## Commands

```bash
npm install
npm run dev
npm run build
npm run preview
npm run typecheck
```

## API target

- Dev requests use `/api/v1/*` and are proxied by Vite.
- Configure proxy target in `apps/web/.env`:
  - `VITE_API_PROXY_TARGET=http://localhost:8000`
- Copy from `apps/web/.env.example` and set the backend port you actually run.

See `instructions/05-frontend/` for UX flows and architecture.
