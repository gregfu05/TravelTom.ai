# Runbooks

## Common failures

- Database connection failure
  - Check `DATABASE_URL`.
  - Verify Postgres service health.
- Chat 429
  - Capture HTTP status, `error.code`, `details.retry_after_seconds`,
    `X-Trace-ID`, and `Retry-After`.
  - If `error.code=rate_limit_exceeded`, inspect TravelTom limiter logs for the
    same trace ID before changing provider settings.
  - If `error.code=provider_rate_limited`, inspect provider quota/rate-limit
    status before changing TravelTom throttling.
- LLM timeout
  - Check Azure OpenAI status.
  - Increase timeout temporarily.
- Recommendation service error
  - Verify retrieval backend connectivity.
  - Run deterministic ranking tests.
- Model quality regression alert
  - Verify latest offline evaluation report and gate results.
  - Compare current production model version against previous blue revision.

## Migrations

- Always run `alembic upgrade head` before deploy.
- Use `alembic downgrade -1` for rollback.

## Incident checklist

- Confirm scope of impact.
- Collect logs and trace IDs.
- Identify whether incident is service outage, data issue, or model-quality issue.
- Mitigate (disable feature flags, reduce traffic, or switch to previous blue revision).
- If model-related, roll back to previous model version and re-run smoke checks.
- Document root cause and follow-up tasks.

## Blue-green rollback triggers

- Trigger immediate rollback when any condition is met:
  - Smoke tests fail on green.
  - `/api/v1/chat` P95 latency stays above 2.0s for 15 minutes.
  - `/api/v1/recommendations/query` P95 latency stays above 1.5s for 15 minutes.
  - 7-day CTR proxy drops by more than 20% versus trailing 28-day baseline.
