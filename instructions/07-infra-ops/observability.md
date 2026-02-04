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

## Metrics

- P95 latency for `/api/v1/chat` and `/api/v1/recommendations/query`.
- Error rates by endpoint.
- Tool failure counts.

## Dashboards

- Latency and error dashboard.
- Recommender coverage and CTR proxy.

