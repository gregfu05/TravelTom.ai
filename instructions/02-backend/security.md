# Security

## MVP stance

- Local dev may run with `AUTH_ENABLED=false`.
- Current implemented auth/session lifecycle is local TravelTom email/password only.
- When `AUTH_ENABLED=true`, bearer-token auth is enforced for protected endpoints.
- Local email/password auth is enabled by configuring `LOCAL_AUTH_TOKEN_SECRET`.
- Local bearer tokens use both an absolute expiry (`LOCAL_AUTH_TOKEN_TTL_SECONDS`) and
  an idle timeout (`LOCAL_AUTH_TOKEN_IDLE_TIMEOUT_SECONDS`).
- Use a single backend API key for internal tools if needed.
- Chat rate limiting is configured via `CHAT_RATE_LIMIT`.
- Secrets are stored in environment variables only.

## Final stance

- Authentication provider: Azure AD B2C (OIDC).
- Authorization via session ownership.
- Per-user rate limits and abuse detection.
- Deployment/provider-specific auth integration is deferred until later deployment work.

## Implemented backend path

- Local email/password account creation and password verification are library-backed
  through `fastapi-users` and `pwdlib`.
- TravelTom local bearer-token signing/verification uses `PyJWT`.
- Local bearer tokens are backed by persisted `auth_sessions` rows so logout and timeout
  checks are enforced server-side.
- Chat rate limiting uses the `limits` library.
- `POST /api/v1/auth/signup` creates a local account and returns a TravelTom bearer token.
- `POST /api/v1/auth/login` authenticates a local account and returns a TravelTom bearer token.
- `GET /api/v1/auth/me` returns the authenticated user for a valid bearer token.
- `POST /api/v1/auth/logout` revokes the current local bearer token.
- `POST /api/v1/chat` requires an authenticated bearer token when auth is enabled.
- `POST /api/v1/recommendations/query` requires an authenticated bearer token when auth is enabled.
- `GET /api/v1/health` remains public.
- Chat session ownership is enforced with `sessions.user_id`.
- Request-body `user_id` is deprecated and ignored by the backend.
- Logged-out tokens and idle-timed-out tokens are rejected with `401 Unauthorized`.

## Local token lifecycle

- Local auth sessions are persisted in `auth_sessions`.
- Each token carries a `jti` that resolves to a persisted auth session.
- Library-backed local credential validation does not replace server-side session checks.
- Absolute token expiry is controlled by `LOCAL_AUTH_TOKEN_TTL_SECONDS`.
- Idle timeout is controlled by `LOCAL_AUTH_TOKEN_IDLE_TIMEOUT_SECONDS`.
- Successful local-authenticated requests extend the idle timeout window.
- `POST /api/v1/auth/logout` revokes only the current local bearer token.
- Azure AD B2C bearer validation remains a future deployment concern for this lifecycle.

## Secrets handling

- Store secrets in `.env` only for local dev.
- Use Azure Key Vault in production.
- Only the API service managed identity may read production secrets.
- Rotate production secrets at least every 90 days.
- Never log secrets or raw user messages.

## PII considerations

- Avoid collecting PII by default.
- If user accounts are enabled, store minimal data and support deletion requests.
- Deletion SLA for user-associated analytics data: 30 days.
- Encrypt data at rest via managed Postgres.

## Rate limiting and abuse

- Use per-user rate limits when auth is enabled.
- Fall back to IP-based chat limits only when auth is disabled for local dev.
- Add per-session limits for later session-backed endpoints as needed.
- Log rejected requests as security events.
