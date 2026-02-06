# Event Pipeline

## MVP

- Events are validated and stored in PostgreSQL `events` table.
- Event streaming beyond DB is out of scope for MVP.
- Batch exports run weekly via `scripts/export_events.py`.
- Retain 90 days of events in DB.

## Final

- Dual write is mandatory: Postgres for operational queries, Event Hub for streaming analytics.
- Retain raw events in Blob Storage for 1 year.
- Stream processing feeds dashboards and evaluation datasets.

## Privacy

- Avoid PII in payloads.
- Hash any user identifiers used for analytics.
- Deletion SLA for user-associated events is 30 days across all stores.
