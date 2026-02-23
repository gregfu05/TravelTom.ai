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
- Added planner route `/planner` with `ChatView` and message flow.
- Added client session store in `src/store/session.ts` for chat state.
- Added recommendations rendering in planner from `/api/v1/chat` responses
  (latest response snapshot) with a compact top-5 presentation.

## Component structure

- `AppShell`
- `TopNav`
- `HomePage`
- `WhyTravelTomPage`
- `HowItWorksPage`
- `PlannerPage`
- `ChatView`
- `RecommendationsPanel` (currently embedded inside `ChatView`)
- `ShortlistView`
- `ItineraryView`
- `BookingStub`

## Routing stance

- Current MVP baseline uses route-level separation for marketing and orientation pages:
  - `/`
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

## UI library

- Optional acceleration: MUI or Chakra UI (per design doc).

## API client

- Centralized `apiClient` with base URL `/api/v1`.
- Request/response schemas validated with Zod (frontend) mirroring Pydantic.
- Normalize non-2xx responses into a typed `ApiClientError` for predictable UI handling.
- Map backend snake_case chat response fields to frontend camelCase models in the API client.
- Implement `sendChatMessage` for `/api/v1/chat`, append assistant responses,
  and map recommendation payloads for planner rendering.
- Vite dev proxy target is configurable via `VITE_API_PROXY_TARGET` in
  `apps/web/.env` (loaded by Vite config).

## Homepage scope

- Header with primary navigation and API status.
- Hero section with CTA links to dedicated `why` and `how` pages.
- Supporting sections: planner preview and handoff panel for next implementation steps.
- Designed to hand off directly into upcoming chat/planner implementation work.

## Error and loading states

- Global error banner for API failures.
- Inline loading state for chat requests and retry support on failed sends.
- Recommendation panel empty state when `recommendations` is empty in latest
  response.
- Recommendation panel presents only top 5 items with collapsed rationale to
  reduce clutter.
- Retry button on chat failures.
- Homepage API status states: checking, online, unreachable.
- Chat screen states include:
  - Empty state before first message
  - Loading state while awaiting `/api/v1/chat`
  - Error state with retry for the last failed send

## Analytics

- Centralized `trackEvent` helper that posts to `/api/v1/events`.
- Include `session_id`, `message_id`, and `idempotency_key` in all events.
