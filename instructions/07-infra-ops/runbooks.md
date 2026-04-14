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
- `Deploy Prod` runs migrations before revision smoke tests.

## Incident checklist

- Confirm scope of impact.
- Collect logs and trace IDs.
- Identify whether incident is service outage, data issue, or model-quality issue.
- Mitigate (disable feature flags, reduce traffic, or switch to previous blue revision).
- If model-related, roll back to previous model version and re-run smoke checks.
- Document root cause and follow-up tasks.

## Deployment workflow references

- Publish artifacts: `.github/workflows/publish-images.yml`
- Dev deployment: `.github/workflows/deploy-dev.yml`
- Prod deployment: `.github/workflows/deploy-prod.yml`
- Revision rollback: `.github/workflows/rollback-container-app.yml`
- Dev ML train: `.github/workflows/ml-train-dev.yml`
- Dev ML evaluate: `.github/workflows/ml-evaluate-dev.yml`
- Dev ML promote: `.github/workflows/ml-promote-dev.yml`

## Smoke checks

- API: `pwsh ./scripts/smoke-api.ps1 -BaseUrl https://<api-url>`
- Web: `pwsh ./scripts/smoke-web.ps1 -BaseUrl https://<web-url>`

## Revision rollback procedure

1. Find the previous known-good revision names for `api` and `web`.
2. Run `Rollback Container Apps`.
3. Re-run the smoke scripts against the restored URLs.
4. If the rollback is migration-sensitive, assess whether the DB schema must be downgraded before re-enabling the failed revision.

## Blue-green rollback triggers

- Trigger immediate rollback when any condition is met:
  - Smoke tests fail on green.
  - `/api/v1/chat` P95 latency stays above 2.0s for 15 minutes.
  - `/api/v1/recommendations/query` P95 latency stays above 1.5s for 15 minutes.
  - 7-day CTR proxy drops by more than 20% versus trailing 28-day baseline.

## Dev MLOps promote and rollback

Promotion sequence:

1. Run `ML Train Dev` to publish the candidate artifact, metrics, and manifest.
2. Run `ML Evaluate Dev` and confirm the offline gate output is `promote=true`.
3. Run `ML Promote Dev` to update the dev API Container App with:
   - `TRAVELTOM_ML_RANKER_ARTIFACT_URI`
   - `TRAVELTOM_ML_RANKER_PROMOTED_VERSION`
4. Run API smoke checks and a recommendation request against dev.

Rollback sequence:

1. Identify the previous promoted model version and artifact URL in the
   `ml-artifacts` container.
2. Re-run `ML Promote Dev` with the previous model version.
3. If needed, reactivate the previous Container App revision with
   `Rollback Container Apps`.
4. Re-run API smoke checks and verify heuristic fallback if artifact loading fails.
