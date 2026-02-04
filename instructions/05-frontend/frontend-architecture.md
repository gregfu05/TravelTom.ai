# Frontend Architecture

## Component structure

- `AppShell`
- `ChatView`
- `MessageList`
- `MessageInput`
- `RecommendationsPanel`
- `RecommendationCard`
- `ShortlistView`
- `ItineraryView`
- `BookingStub`

## State management

- Use Zustand for session state and shortlist.
- Use React Query for API calls and caching.
- Keep server state in React Query; UI state in Zustand.

## UI library

- Optional acceleration: MUI or Chakra UI (per design doc).

## API client

- Centralized `apiClient` with base URL `/api/v1`.
- Request/response schemas validated with Zod (frontend) mirroring Pydantic.

## Error and loading states

- Global error banner for API failures.
- Inline loading placeholders for recommendations.
- Retry button on chat failures.

## Analytics

- Centralized `trackEvent` helper that posts to `/api/v1/events`.
- Include `session_id`, `message_id`, and `idempotency_key` in all events.

