# Security

## MVP stance

- Local dev may run with `AUTH_ENABLED=false`.
- When `AUTH_ENABLED=true`, bearer-token auth is enforced for protected endpoints.
- Use a single backend API key for internal tools if needed.
- Chat rate limiting is configured via `CHAT_RATE_LIMIT`.
- Secrets are stored in environment variables only.

## Final stance

- Authentication provider: Azure AD B2C (OIDC).
- Authorization via session ownership.
- Per-user rate limits and abuse detection.

## Implemented backend path

- Auth library: `fastapi-azure-auth`.
- Chat rate limiting uses the `limits` library.
- `POST /api/v1/chat` requires an authenticated bearer token when auth is enabled.
- `POST /api/v1/recommendations/query` requires an authenticated bearer token when auth is enabled.
- `GET /api/v1/health` remains public.
- Chat session ownership is enforced with `sessions.user_id`.
- Request-body `user_id` is deprecated and ignored by the backend.

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
