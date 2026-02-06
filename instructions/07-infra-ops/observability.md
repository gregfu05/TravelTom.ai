# Observability

## Logging

- Structured JSON logs with fields: `timestamp`, `level`, `service`, `trace_id`, `span_id`, `message`, `context`.
- Do not log secrets or raw user messages.

## Tracing

- Use OpenTelemetry SDK in backend.
- Propagate trace IDs from frontend to backend via headers.
- Create spans for:
  - Chat request
  - Recommendation retrieval
  - Ranking
  - LLM call

## Service metrics and SLOs

- P95 latency target:
  - `/api/v1/chat` <= 2.0s
  - `/api/v1/recommendations/query` <= 1.5s
- Error rates by endpoint.
- Tool failure counts.

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
