# Observability

## Logging

- Structured JSON logs with fields: `timestamp`, `level`, `service`, `trace_id`, `span_id`, `message`, `context`.
- Do not log secrets or raw user messages.
- For chat 429s, log whether the source is `traveltom` or `provider`.
- TravelTom limiter logs should include `chat_rate_limit`, caller identity key,
  retry-after, client host, and trace ID.
- Chat provider degradation logs should include:
  - `provider_stage_succeeded`
  - `provider_stage_failed`
  - `provider_stage_skipped`
  - `planner_execution_failed`
  - `planner_unavailable`
- Azure deployment workflows should log:
  - target image tag
  - computed revision suffix
  - previously active revision names

## Tracing

- Use OpenTelemetry SDK in backend.
- Propagate trace IDs from frontend to backend via headers.
- Export backend telemetry to Azure Monitor via `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Frontend uses Application Insights when `VITE_APPINSIGHTS_CONNECTION_STRING` is set.
- Create spans for:
  - Chat request
  - Recommendation retrieval
  - Ranking
  - planner stage
  - composer stage

Current implementation boundary:
- Backend bootstrap installs JSON logging and Azure Monitor/OpenTelemetry export in `apps/api/app/main.py`.
- Request correlation uses `X-Trace-ID`.
- Frontend sends `X-Trace-ID` on each API request and records API failures in App Insights.

## Service metrics and SLOs

- P95 latency target:
  - `/api/v1/chat` <= 2.0s
  - `/api/v1/recommendations/query` <= 1.5s
- Error rates by endpoint.
- Tool failure counts.
- Planner/composer failure counts and circuit-open events.

## Model-quality metrics

- Offline NDCG@10 and MAP@10 from scheduled evaluation runs.
- Coverage pass rate using thresholds from `03-recommender/evaluation.md`.
- 7-day CTR proxy and 28-day baseline.

## Drift detection

- Feature drift check (weekly): PSI on core ranking features (`similarity`, `price`, `rating`, `popularity`).
  - Warning: PSI >= 0.20
  - Critical: PSI >= 0.30
- Score distribution drift (weekly): KS distance between current and baseline score distributions.
  - Warning: KS >= 0.15
  - Critical: KS >= 0.20
- Behavior drift (daily): 7-day CTR proxy delta vs trailing 28-day baseline.
  - Critical: drop > 20%

## Alerting and ownership

- Warning alerts create an ops issue in the repository and are reviewed within 48 hours.
- Critical alerts trigger immediate rollback assessment.
- Primary owner: backend/recommender maintainer on duty.

## Dashboards

- Latency and error dashboard.
- Recommender coverage, CTR proxy, and drift dashboard.
- Chat runtime dashboard:
  - planner success/failure/skip counts
  - composer success/failure/skip counts
  - deterministic-only versus provider-assisted traffic split
- Azure dashboard seed file: `infra/azure/dashboards.json`.

## Azure infra metadata

- Azure resources should be tagged consistently for filtering and cost review:
  - `app`
  - `environment`
  - `managedBy`
  - `owner`
  - `stack`
