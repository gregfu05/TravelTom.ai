# UX Flows

## Primary flow

1. User lands on the homepage and selects the planner entry CTA.
2. User can move to `/login` or `/signup` from shared site navigation and can
   always return to `/` from those auth routes.
3. User optionally reviews `Why TravelTom` and `How It Works` route pages.
4. User opens `/planner` and enters a chat message.
5. Frontend sends the request to `/api/v1/chat` with `session_id` and `message_id`.
6. If the browser already has a backend-backed planner session, frontend
   hydrates transcript, recommendations, and server state from
   `GET /api/v1/chat/{session_id}` before the next turn.
7. Assistant response is appended to the message list and recommendations are rendered from the latest response payload.
8. User saves items (destinations, hotels, flights) to shortlist.
9. User views generated itinerary.
10. User clicks booking stub to simulate conversion.

## Screens and states

- Homepage
  - Default marketing state with planner CTA
  - API status state (`checking`, `online`, `unreachable`) from health probe
  - Primary navigation remains accessible on mobile through a dedicated menu path
  - Responsive layout on mobile and desktop breakpoints
- Auth screens
  - Routes: `/login`, `/signup`
  - Shared TravelTom navigation and a visible body-level return action to `/`
  - Branded entry composition with supporting context panel plus primary form
  - Success returns user to a preserved protected-route target when present,
    otherwise `/planner`
  - Switching between login and signup preserves the same return target
  - Authenticated users visiting auth routes are redirected to `/planner`
- Why TravelTom page
  - Product value and trust rationale
  - CTA path to the `How It Works` page
- How It Works page
  - User journey flow
  - System flow explanation
  - CTA back to homepage/planner entry
- Chat screen
  - Route: `/planner`
  - Empty state
  - Empty-state chips encourage either:
    - broad destination exploration prompts, or
    - concrete hotel/flight prompts with destination, dates, and budget
  - Conversation progression supports:
    - natural greeting
    - progressive slot capture
    - search-type clarification when trip details are known but item type is not
    - grounded results or explicit no-results refinement guidance
  - Loading state (assistant typing)
  - Error state
  - Retry action for last failed message
- Recommendations panel
  - Split-pane planner layout: chat in primary pane, recommendations in a
    secondary rail so the conversation stays visible
  - Compact top-5 list from latest `/api/v1/chat` response
  - Constrained-height recommendation rail with internal scroll
  - Mobile path uses a header-level picks button that opens a drawer version of
    the same recommendations list
  - Header-level metadata and collapsible per-item rationale
  - Card metadata for item name, score, and available attributes (e.g., city, stars)
  - Empty state handled by chat assistant clarification/error copy
- Shortlist view
  - Add/remove items
  - Compare saved items
  - Notes for saved items
- Itinerary view
  - Day-by-day breakdown
  - Editable order (optional for MVP)
- Booking stub
  - CTA to simulate booking with a confirmation toast

## Analytics hooks

- Impression events when items are visible.
- Click events on items and booking CTA.
- Save/remove events on shortlist.
