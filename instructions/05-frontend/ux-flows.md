# UX Flows

## Primary flow

1. User lands on the homepage and selects the planner entry CTA.
2. User optionally reviews `Why TravelTom` and `How It Works` route pages.
3. User opens `/planner` and enters a chat message.
4. Frontend sends the request to `/api/v1/chat` with `session_id` and `message_id`.
5. Assistant response is appended to the message list, including loading and error handling states.
6. User saves items (destinations, hotels, flights) to shortlist.
7. User views generated itinerary.
8. User clicks booking stub to simulate conversion.

## Screens and states

- Homepage
  - Default marketing state with planner CTA
  - API status state (`checking`, `online`, `unreachable`) from health probe
  - Responsive layout on mobile and desktop breakpoints
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
  - Loading state (assistant typing)
  - Error state
  - Retry action for last failed message
- Recommendations panel
  - List view with ranking and explanations
  - Tabs or filters for destinations/hotels/flights
  - Empty state with fallback prompt
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
