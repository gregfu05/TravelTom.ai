# ADR: OpenTelemetry with structured JSON logs

- Status: Accepted
- Date: 2026-02-04

## Context

We need consistent observability for chat and recommendation latency, errors, and traces.

## Decision

Adopt OpenTelemetry for tracing and metrics, and structured JSON logging with correlation IDs. P95 latency for chat and recommendation endpoints is a tracked metric.

## Alternatives considered

- Logging only: Insufficient for distributed tracing.
- Vendor-specific telemetry only: Limits portability.

## Consequences

- Positive: Consistent tracing and metrics, easy export to Azure App Insights.
- Negative: Additional configuration and instrumentation.
- Risks: Inconsistent correlation if IDs are not enforced; mitigate with middleware.

## Notes

See `07-infra-ops/observability.md`.

