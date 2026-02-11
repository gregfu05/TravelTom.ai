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
- Standalone informational routes:
  - `/planner`
  - `/why-traveltom`
  - `/how-it-works`
- Typed API client for `/api/v1` integration

## Commands

```bash
npm install
npm run dev
npm run build
npm run preview
npm run typecheck
```

See `instructions/05-frontend/` for UX flows and architecture.
