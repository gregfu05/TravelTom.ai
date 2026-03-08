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

### POST /api/v1/auth/signup

Creates a local TravelTom account and returns a bearer token.

Current scope:

- End-to-end auth/session lifecycle in the current backend build is local only.
- Azure AD B2C deployment/provider work is deferred.

Request:

```json
{
  "email": "traveler@example.com",
  "password": "string"
}
```

Response:

```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "idle_timeout_in": 1800,
  "user": {
    "id": "string",
    "email": "traveler@example.com"
  }
}
```

Implementation notes (current):

- Endpoint lives in `apps/api/app/api/v1/auth.py`.
- API request/response schemas live in `apps/api/app/schemas/api/auth.py`.
- Shared auth runtime schemas live in `apps/api/app/schemas/auth.py`.
- Local account creation and token issuance live in `apps/api/app/services/auth.py`.
- Local auth-session persistence lives in `apps/api/app/repositories/auth_sessions.py`.

### POST /api/v1/auth/login

Authenticates a local TravelTom account and returns a bearer token.

Request and response match `POST /api/v1/auth/signup`.

### POST /api/v1/auth/logout

Revokes the current local TravelTom bearer token.

Auth:

- Requires `Authorization: Bearer <token>`.
- Available only for TravelTom local bearer tokens.

Response: `204 No Content`

### GET /api/v1/auth/me

Returns the current authenticated user for a valid bearer token.

Auth:

- Accepts a TravelTom-issued local bearer token.
- Local tokens must reference an active persisted auth session and may be rejected
  after logout, absolute expiry, or idle timeout.
- Azure AD B2C bearer-token support remains deferred for deployment work.

Response:

```json
{
  "id": "string",
  "email": "traveler@example.com"
}
```

### GET /api/v1/health

Liveness check for the API service.

Response:

```json
{
  "status": "ok"
}
```

Implementation notes (current):

- Endpoint lives in `apps/api/app/api/v1/health.py` (thin router, HTTP contract only).
- Health response schema lives in `apps/api/app/schemas/api/health.py`.
- Health payload construction lives in `apps/api/app/services/health_status.py`.

### POST /api/v1/chat

Primary chat endpoint. Orchestrates tool calls and returns a response.

Auth:

- Accepts `Authorization: Bearer <token>` for TravelTom local bearer tokens.
- Requires a bearer token when backend auth is enabled.
- `user_id` is deprecated and ignored when sent; user identity is derived from the bearer token.
- Local tokens must reference an active persisted auth session and may be rejected
  after logout or idle timeout.

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

Implementation notes (current):

- Endpoint lives in `apps/api/app/api/v1/chat.py` (thin router, orchestration + persistence wiring only).
- Orchestrator runtime is LLM-first for intent interpretation, clarification strategy, and response composition.
- Recommendation retrieval remains tool-first and deterministic; router never returns model-invented recommendation items.
- Request/response Pydantic schemas live in `apps/api/app/schemas/api/chat.py` (`ChatRequest`, `ChatResponse`, `ChatRecommendation`, `ClientContext`).
- Chat transaction boundary lives in `apps/api/app/services/chat_uow.py`.
- Session/message/recommendation persistence lives in `apps/api/app/repositories/chat.py`.
- Authenticated user resolution lives in `apps/api/app/repositories/users.py`.
- Shared auth principal schema lives in `apps/api/app/schemas/auth.py`.
- Shared orchestrator response schema lives in `apps/api/app/schemas/orchestrator.py`.
- Session identity/state helpers live in `apps/api/app/services/chat_persistence.py`.
- `session_id` is treated as an opaque client id and mapped to an internal deterministic UUID for DB persistence.
- When auth is enabled, session ownership is enforced against `sessions.user_id`.
- Each call persists:
  - updated `sessions.state_json`
  - one `messages` row for the user message
  - one `messages` row for the assistant message
  - one `recommendations` snapshot row (empty `results` is valid in placeholder mode)
- Tool and model failure behavior:
  - planner/model output failures fall back to deterministic orchestration guards
  - tool timeout/invalid payload/empty results return explicit safe assistant copy

### POST /api/v1/recommendations/query

Deterministic recommendation retrieval and ranking. Internal endpoint used by orchestrator and test tooling.

Auth:

- Accepts TravelTom local bearer tokens.
- Requires `Authorization: Bearer <token>` when backend auth is enabled.
- Local tokens must reference an active persisted auth session.

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
  "max_results": 20,
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

Notes:
- `max_results` default is 20.
- `max_results` hard cap is 50 (debug and evaluation use only).
- Endpoint lives in `apps/api/app/api/v1/recommendations.py` (thin router, DI + HTTP mapping only).
- API request/response schemas live in `apps/api/app/schemas/api/recommendations.py`.
- Recommendation tool execution/validation lives in `apps/api/app/services/recommendation_query.py`.
- Service validates tool payloads using `app/schemas/tools/recommendations.py` contracts.
- In placeholder mode, results may be an empty list while recommender integration is pending.

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
- 422 Unprocessable Entity: Request schema validation error (FastAPI default).
- 401 Unauthorized: Missing or invalid auth.
- 403 Forbidden: Authenticated caller is not allowed to access the resource.
- 404 Not Found: Missing resource.
- 409 Conflict: Idempotency conflict.
- 429 Too Many Requests: Rate limit.
- 500 Internal Server Error: Unhandled errors.
