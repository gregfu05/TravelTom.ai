# Frontend Architecture

## UI design skill

- For any UI implementation or redesign, follow `ui-design-skill.md` in this folder.
- Treat visual quality as a core requirement, not an optional polish pass.

## MVP baseline (2026-02-10)

- Frontend is scaffolded with React + TypeScript + Vite.
- Root app wiring includes `QueryClientProvider` for React Query in `src/main.tsx`.
- Initial UI foundation is `AppShell` + `HomePage` with responsive, tokenized global styles.
- Homepage includes a health check indicator backed by `GET /api/v1/health`.
- Added dedicated marketing routes for `/why-traveltom` and `/how-it-works`.
- Added branded auth entry routes `/login` and `/signup` with shared site chrome
  and an explicit return path back to the landing page.
- Added planner route `/planner` with `ChatView` and message flow.
- Added client session store in `src/store/session.ts` for chat state.
- Added recommendations rendering in planner from `/api/v1/chat` responses
  (latest response snapshot) with a split chat + recommendation rail layout so
  chat stays visible while recommendation cards are present.
- Planner empty-state suggestion chips and helper copy now align with backend
  recommendation timing:
  broad destination exploration prompts are valid, while hotel and flight
  prompts should include destination, dates, and budget.

## Frontend structure

- Route pages and reusable components are folderized under `src/pages/<Name>/`
  and `src/components/<Name>/`, with their colocated `*.test.*` files kept
  beside the implementation.
- Planner-specific UI and non-UI logic live under `src/features/planner/`
  instead of the shared `components/` folder.
- Shared route registration lives in `src/app/routes.tsx`; `src/App.tsx`
  remains shell + router composition only.
- Styles are split under `src/styles/` by concern (`tokens`, `base`,
  `marketing`, `auth`, `planner`, `responsive`) and loaded through
  `src/styles/index.css`.

## Component boundaries

- `AppShell` and `TopNav` remain shared app-level chrome.
- Marketing and auth routes each own their page modules under `src/pages/`.
- Planner route uses `features/planner/components/ChatView` as the route-level
  composition point.
- Planner conversation rendering, recommendation surfaces, hydration helpers,
  and chat error state helpers are separate planner modules rather than one
  oversized shared component file.

## Routing stance

- Current MVP baseline uses route-level separation for marketing and orientation pages:
  - `/`
  - `/login`
  - `/signup`
  - `/planner`
  - `/why-traveltom`
  - `/how-it-works`
- Chat + recommendations are implemented on `/planner`; shortlist/itinerary/booking
  remain upcoming route-level capabilities.

## State management

- Use Zustand for session state and shortlist.
- Use React Query for API calls and caching.
- Keep server state in React Query; UI state in Zustand.
- Current chat implementation stores `sessionId`, `messages`,
  `latestRecommendations`, send status, and error state in Zustand
  (`src/store/session.ts`).
- Store and domain helpers must not depend on shared UI component folders.
  Planner error-state logic now lives under `src/features/planner/model/`.

## UI library

- Optional acceleration: MUI or Chakra UI (per design doc).

## Frontend test stack

- Use `Vitest` with `jsdom` for frontend unit and DOM/component tests.
- Use React Testing Library for route, page, and interaction coverage.
- Use Playwright for frontend browser smoke coverage of the protected planner flow.
- Prefer deterministic API mocking in frontend tests instead of live backend coupling.
- Frontend coverage should include shipped routes, auth entry flows, planner chat states,
  navigation health/logout behavior, and persisted session hydration.

## API client

- Centralized `apiClient` with base URL `/api/v1`.
- Serialize JSON request bodies in one shared helper inside `apiClient`; call
  sites should pass plain objects instead of pre-stringified payloads.
- Request/response schemas validated with Zod (frontend) mirroring Pydantic.
- Normalize non-2xx responses into a typed `ApiClientError` for predictable UI handling.
- Parse structured 429 metadata, including `Retry-After` and
  `details.retry_after_seconds`, before rendering chat recovery UI.
- Map backend snake_case chat response fields to frontend camelCase models in the API client.
- Implement `sendChatMessage` for `/api/v1/chat`, append assistant responses,
  and map recommendation payloads for planner rendering.
- Vite dev proxy target is configurable via `VITE_API_PROXY_TARGET` in
  `apps/web/.env` (loaded by Vite config).

## Homepage scope

- Header with primary navigation and API status.
- Hero section with CTA links to dedicated `why` and `how` pages.
- Supporting sections: planner preview and current-state CTA into the live planner.
- Designed to orient users quickly and move them into the active product flow.

## Error and loading states

- Global error banner for API failures.
- Inline loading state for chat requests and retry support on failed sends.
- Recommendation panel empty state when `recommendations` is empty in latest
  response.
- Recommendation rail presents only top 5 items with collapsed per-item
  rationale, constrained panel height, and internal scrolling.
- Mobile recommendation access is provided through a header-level picks button
  that opens the planner drawer.
- Retry button on chat failures.
- Distinguish TravelTom cooldowns from provider quota failures in planner chat UX.
- Homepage API status states: checking, online, unreachable.
- Auth routes reuse the main TravelTom theme, typography, and navigation
  instead of standalone form-only styling.
- Auth success redirects honor a preserved protected-route target across the
  login/signup switch; direct auth entry defaults to `/planner`.
- Shared navigation must remain usable on mobile; if desktop nav links are
  hidden at smaller breakpoints, a replacement mobile path is required.
- Chat screen states include:
  - Empty state before first message
  - Loading state while awaiting `/api/v1/chat`
  - Error state with retry for the last failed send
  - TravelTom-owned cooldown state that disables send/retry until the cooldown expires
  - Provider quota/rate-limit state with provider-specific guidance and no blind retry

## Analytics

- Centralized `trackEvent` helper that posts to `/api/v1/events`.
- Include `session_id`, `message_id`, and `idempotency_key` in all events.
