# Data Model

## Core tables

### users

- id (uuid, pk)
- auth_issuer (text, nullable)
- external_subject (text, nullable, unique with auth_issuer)
- email (text, unique, nullable)
- password_hash (text, nullable for non-local identities)
- created_at (timestamptz)

### auth_sessions

- id (uuid, pk)
- user_id (uuid, fk users.id)
- auth_issuer (text)
- expires_at (timestamptz)
- idle_expires_at (timestamptz)
- last_seen_at (timestamptz)
- revoked_at (timestamptz, nullable)
- revoked_reason (text, nullable)
- created_at (timestamptz)

Indexes:
- idx_auth_sessions_user_id
- idx_auth_sessions_revoked_at

### sessions

- id (uuid, pk)
- user_id (uuid, fk users.id, nullable)
- state_json (jsonb)
- created_at (timestamptz)
- updated_at (timestamptz)

Indexes:
- idx_sessions_user_id

### messages

- id (uuid, pk)
- session_id (uuid, fk sessions.id)
- role (text: user|assistant|system)
- content (text)
- created_at (timestamptz)

Indexes:
- idx_messages_session_id

### catalog_items

- id (uuid, pk)
- item_type (text: destination|hotel|flight)
- name (text)
- description (text)
- location_city (text)
- location_country (text)
- latitude (numeric)
- longitude (numeric)
- price (numeric)
- rating (numeric)
- tags (text[])
- metadata_json (jsonb)
- created_at (timestamptz)
- updated_at (timestamptz)

Recommended metadata (by type):

- destination: `popular_seasons`, `avg_nightly_price`, `activities`
- hotel: `star_rating`, `amenities`, `room_types`
- flight: `origin`, `destination`, `departure_time`, `arrival_time`, `duration_minutes`, `stops`, `layover_minutes`, `airline`

Indexes:
- idx_catalog_type
- idx_catalog_location_city
- idx_catalog_rating
- gin_catalog_tags (GIN on tags)

### embeddings (pgvector)

- id (uuid, pk)
- item_id (uuid, fk catalog_items.id)
- embedding (vector)
- model_name (text)
- created_at (timestamptz)

Indexes:
- ivfflat or hnsw index on embedding

### recommendations (cache table, disabled by default)

- id (uuid, pk)
- session_id (uuid, fk sessions.id)
- query_hash (text)
- results_json (jsonb)
- ranking_version (text)
- created_at (timestamptz)

### events

- id (uuid, pk)
- event_id (text, unique)
- event_type (text)
- event_version (int)
- occurred_at (timestamptz)
- received_at (timestamptz)
- session_id (uuid, required)
- user_id (uuid, nullable)
- idempotency_key (text)
- payload (jsonb)

Indexes:
- idx_events_type_time
- idx_events_session_time
- idx_events_idempotency (unique on session_id + event_type + idempotency_key)

## Notes

- Use UUIDs for all primary keys.
- Store session state as JSONB; validate with Pydantic before persist.
- Use pgvector for embedding similarity in MVP.
- ORM models live in `apps/api/app/db/models/` and are registered via `Base.metadata` for Alembic.
