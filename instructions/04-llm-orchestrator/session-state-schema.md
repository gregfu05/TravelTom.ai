# Session State Schema

Source of truth: `apps/api/app/schemas/state.py`

## Canonical schema (v1)

```json
{
  "state_version": "v1",
  "session_id": "string",
  "user_id": "string?",
  "constraints": {
    "origin": "string?",
    "destination": "string?",
    "dates": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
    "trip_length_days": 7,
    "budget": {"min": 1000, "max": 2500, "currency": "USD"},
    "party_size": {"adults": 2, "children": 0}
  },
  "preferences": {
    "weighted_interests": {"museums": 0.8, "food": 0.6},
    "dislikes": ["red_eye_flights", "long_layovers"]
  },
  "entities": {"destinations": ["Lisbon"]},
  "shortlist": ["item_id"],
  "itinerary": {"days": []},
  "status": "explore|refine|itinerary|booking",
  "last_recommendation_version": "heuristic-v1",
  "last_message_at": "2026-02-04T12:00:00Z"
}
```

## Validation constraints

- Unknown fields are rejected (`extra="forbid"` on all nested models).
- `constraints.dates.end` must be on or after `constraints.dates.start`.
- `constraints.budget.max` must be greater than or equal to `constraints.budget.min`.
- `constraints.party_size.adults >= 1` and `children >= 0`.
- `preferences.weighted_interests.*` must be in range `[0, 1]`.
- `status` is an enum: `explore`, `refine`, `itinerary`, `booking`.

## Evolution rules

- Additive changes are allowed within `state_version = "v1"`.
- Breaking changes require a new `state_version`.
- Persist only validated state objects.

## Persistence strategy

- Store canonical state in `sessions.state_json`.
- Re-validate before save and after read when state is loaded into runtime.

