# ADR: Versioned event schema with idempotency

- Status: Accepted
- Date: 2026-02-04

## Context

TravelTom relies on event logging for evaluation and analytics. Events must be consistent, queryable, and idempotent.

## Decision

Adopt a versioned event schema with mandatory fields: `event_id`, `event_type`, `event_version`, `occurred_at`, `session_id`, `user_id` (optional), `idempotency_key`, and `payload`. Events are stored in PostgreSQL for MVP and optionally streamed to Event Hub in final.

## Alternatives considered

- Unversioned events: Hard to evolve safely.
- Multiple event tables: Increases complexity and reduces flexibility.

## Consequences

- Positive: Evolve schemas safely, straightforward analytics.
- Negative: Requires validation and strict typing for payloads.
- Risks: Payload drift; mitigate with schema registry conventions in `06-events-analytics/event-taxonomy.md`.

## Notes

See `06-events-analytics/event-taxonomy.md` and `06-events-analytics/event-pipeline.md`.

