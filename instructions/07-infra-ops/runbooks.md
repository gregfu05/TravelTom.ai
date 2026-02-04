# Runbooks

## Common failures

- Database connection failure
  - Check `DATABASE_URL`.
  - Verify Postgres service health.
- LLM timeout
  - Check Azure OpenAI status.
  - Increase timeout temporarily.
- Recommendation service error
  - Verify retrieval backend connectivity.
  - Run deterministic ranking tests.

## Migrations

- Always run `alembic upgrade head` before deploy.
- Use `alembic downgrade -1` for rollback.

## Incident checklist

- Confirm scope of impact.
- Collect logs and trace IDs.
- Mitigate (disable feature flags or reduce traffic).
- Document root cause and follow-up tasks.

