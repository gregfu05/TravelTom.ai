# UX Flows

## Primary flow

1. User enters chat message.
2. Assistant responds with recommendations and clarifying questions if needed.
3. User saves items (destinations, hotels, flights) to shortlist.
4. User views generated itinerary.
5. User clicks booking stub to simulate conversion.

## Screens and states

- Chat screen
  - Empty state
  - Loading state (assistant typing)
  - Error state
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
