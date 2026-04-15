# Core Runtime

Purpose: cross-cutting runtime concerns used throughout the API app.

Ownership: Backend.

## What Lives Here

- `config.py`: environment-driven settings and defaults.
- `logging.py`: structured logging setup.
- `telemetry.py`: OpenTelemetry and Application Insights wiring.
- `errors.py`: shared API error handling registration.
- `security.py` and `local_auth.py`: auth-related helpers and local token handling.
- `optional_deps.py`: guardrails around optional integrations.

## Use This Layer For

- configuration that must be reused across modules
- shared runtime instrumentation
- common security helpers

Do not use this layer as a generic dumping ground for business logic.

## Related Docs

- `../README.md`
- `../../../../instructions/02-backend/security.md`
- `../../../../instructions/07-infra-ops/observability.md`
