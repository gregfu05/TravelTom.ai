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
  "conversation": {
    "last_requested_slots": ["dates"],
    "last_user_intent": "recommend",
    "last_recommendation_item_type": "hotel",
    "last_recommendation_query": "show me more hotel Lisbon nightlife",
    "last_recommendation_result_ids": ["item_id"]
  },
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
- `conversation.last_user_intent` is `recommend|refine|clarify|null`.
- `conversation.last_recommendation_item_type` is
  `destination|hotel|flight|null`.
- `conversation.last_recommendation_result_ids` is a bounded list of grounded
  recommendation item ids used for duplicate suppression on follow-up turns.
- `status` is an enum: `explore`, `refine`, `itinerary`, `booking`.

## Evolution rules

- Additive changes are allowed within `state_version = "v1"`.
- Breaking changes require a new `state_version`.
- Persist only validated state objects.

## Persistence strategy

- Store canonical state in `sessions.state_json`.
- Re-validate before save and after read when state is loaded into runtime.

## LLM-first state handling notes

- On normal `/api/v1/chat` turns, persisted state changes come from a
  schema-validated `LLMOrchestrationPlan.state_patch` merged through
  `apply_structured_state_patch(...)`.
- Deterministic extraction still runs as a guardrail to enrich missing
  constraints from user text, but primarily as planner hint input and fallback
  state when planner output is missing or invalid.
- Free-form model transcript text is never the source of truth for persisted
  `SessionState`.
- Destination values are deduplicated in `entities.destinations`.
- `constraints.destination` is only filled from validated travel signal:
  assignment-style phrases like `destination: Lisbon` and concise bare replies
  like `Lisbon` are accepted, while greetings and meta questions that merely
  mention `destination` do not mutate `constraints.destination` or
  `entities.destinations`.
- `conversation.last_requested_slots` tracks the most recent progressive
  clarification ask so the assistant can request one next-most-useful detail
  instead of repeating the full core-constraints list, and runtime keeps
  re-asking that same slot until it is actually captured.
- `conversation.last_user_intent` preserves whether the user is trying to
  recommend, refine, or clarify, so a later slot-filling turn can continue the
  prior recommendation flow once the missing details are complete.
- `conversation.last_recommendation_item_type` preserves the effective hotel,
  flight, or destination mode across follow-up turns like `show me more` and
  across clarification turns while those recommendation details are still being
  collected.
- `conversation.last_recommendation_query` preserves the effective recommender
  query text so deterministic carry-forward can keep topical terms on later
  elliptical turns like `another option` or `cheaper`, and can merge later
  slot-filling answers into the same active recommendation thread.
- `conversation.last_recommendation_result_ids` preserves the most recently
  surfaced grounded item ids so follow-up turns like `show me more` can prefer
  unseen results and avoid replaying the same visible list as if it were new.

