# API Design

## Versioning

- Base path: `/api/v1`
- Backward-compatible changes allowed within a version.
- Breaking changes require `/api/v2`.

## Error model

All errors return JSON:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {"optional": "object"},
    "trace_id": "string"
  }
}
```

## Endpoints

### GET /api/v1/health

Liveness check for the API service.

Response:

```json
{
  "status": "ok"
}
```

### POST /api/v1/chat

Primary chat endpoint. Orchestrates tool calls and returns a response.

Request:

```json
{
  "session_id": "string",
  "message_id": "string",
  "user_id": "string?",
  "message": "string",
  "client_context": {
    "timezone": "string",
    "locale": "string",
    "currency": "string"
  }
}
```

Response:

```json
{
  "session_id": "string",
  "message_id": "string",
  "assistant_message": "string",
  "recommendations": [
    {
      "item_id": "string",
      "item_type": "destination|hotel|flight",
      "score": 0.0,
      "rank": 1,
      "explanation": "string",
      "metadata": {}
    }
  ],
  "itinerary": {
    "days": []
  },
  "state": {}
}
```

### POST /api/v1/recommendations/query

Deterministic recommendation retrieval and ranking. Primarily used by orchestrator; can be internal.

Request:

```json
{
  "session_id": "string",
  "query": "string",
  "constraints": {
    "origin": "string?",
    "destination": "string?",
    "dates": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
    "budget": {"min": 0, "max": 0, "currency": "USD"},
    "party_size": {"adults": 1, "children": 0},
    "star_rating_min": 0
  },
  "filters": {},
  "max_results": 50,
  "ranking_version": "string"
}
```

Response:

```json
{
  "results": [
    {
      "item_id": "string",
      "item_type": "destination|hotel|flight",
      "score": 0.0,
      "rank": 1,
      "features": {},
      "explanation": "string"
    }
  ],
  "ranking_version": "string"
}
```

### POST /api/v1/events

Ingests client and server events.

Request:

```json
{
  "event_id": "string",
  "event_type": "string",
  "event_version": 1,
  "occurred_at": "2026-02-04T12:00:00Z",
  "session_id": "string",
  "user_id": "string?",
  "idempotency_key": "string",
  "payload": {}
}
```

Response: `204 No Content` on success.

### GET /api/v1/catalog/search

Search and filter catalog items (used for debugging or admin tooling).

Query params: `q`, `type` (`destination|hotel|flight`), `limit`, `offset`.

### POST /api/v1/shortlists

Creates/updates a shortlist.

Request:

```json
{
  "session_id": "string",
  "items": ["string"],
  "notes": "string?"
}
```

### GET /api/v1/itineraries/{session_id}

Returns the current itinerary for a session.

## Status codes

- 200 OK: Successful request.
- 201 Created: Resource created.
- 204 No Content: Event accepted.
- 400 Bad Request: Validation error.
- 401 Unauthorized: Auth required (final).
- 403 Forbidden: Auth failed (final).
- 404 Not Found: Missing resource.
- 409 Conflict: Idempotency conflict.
- 429 Too Many Requests: Rate limit.
- 500 Internal Server Error: Unhandled errors.
