# Security

## MVP stance

- No end-user authentication required.
- Use a single backend API key for internal tools if needed.
- Basic rate limiting on `/api/v1/chat` and `/api/v1/events`.
- Secrets are stored in environment variables only.

## Final stance

- Authentication provider: Azure AD B2C (OIDC).
- Authorization via session ownership.
- Per-user rate limits and abuse detection.

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

- Use token bucket limits per IP for MVP.
- For final, add per-user and per-session limits.
- Log rejected requests as security events.
