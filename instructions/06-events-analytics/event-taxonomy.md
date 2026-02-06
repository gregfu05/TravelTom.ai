# Event Taxonomy

## Required events (non-negotiable)

- `rec.impression`
- `rec.click`
- `rec.save`
- `rec.dismiss`
- `booking.funnel` (multi-step, even if stubbed)

## Recommended supporting events

- `chat.message_sent`
- `chat.message_received`
- `shortlist.update`
- `itinerary.view`
- `system.error`

## Required fields (all events)

- `event_id` (uuid)
- `event_type`
- `event_version`
- `occurred_at` (ISO timestamp)
- `session_id`
- `user_id` (optional)
- `idempotency_key`
- `payload` (schema varies per event)

## Idempotency

- `idempotency_key` must be unique for a session + event_type.
- Server rejects duplicates with `409`.

## Session correlation

- Every event must include `session_id`.
- `message_id` is required for:
  - `chat.message_sent`
  - `chat.message_received`
  - `rec.impression` events emitted from a chat response

## Example payloads

- `rec.impression`:
  - `items`: list of `item_id`
  - `rankings`: list of `{item_id, rank, score}`
- `rec.click`:
  - `item_id`
  - `rank`
- `rec.save`:
  - `item_id`
  - `rank`
- `booking.funnel`:
  - `step`: `view|start|confirm`
  - `item_id`
