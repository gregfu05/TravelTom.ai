# Session State Schema

## Canonical schema (v1)

```json
{
  "session_id": "string",
  "user_id": "string?",
  "constraints": {
    "origin": "string?",
    "destination": "string?",
    "dates": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
    "trip_length_days": 0,
    "budget": {"min": 0, "max": 0, "currency": "USD"},
    "party_size": {"adults": 1, "children": 0}
  },
  "preferences": {
    "weighted_interests": {"museums": 0.8, "food": 0.6},
    "dislikes": ["red_eye_flights", "long_layovers"]
  },
  "entities": {
    "destinations": ["string"]
  },
  "shortlist": ["item_id"],
  "itinerary": {"days": []},
  "status": "explore|refine|itinerary|booking",
  "last_recommendation_version": "string",
  "last_message_at": "2026-02-04T12:00:00Z"
}
```

## Evolution rules

- Additive changes are allowed in the same version.
- Breaking changes require a new `state_version`.
- All persisted state must pass validation before save.

## Persistence strategy

- Store state in `sessions.state_json`.
- Update on each successful orchestrator run.

## Validation strategy

- Use Pydantic models shared between orchestrator and API schemas.
- Reject invalid states and return a safe error to the client.

