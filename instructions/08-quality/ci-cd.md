# CI/CD

## Minimal CI pipeline

1. Install dependencies.
2. Lint (Python and TS).
3. Type check (mypy, tsc).
4. Run unit and integration tests.

## Security automation

- CodeQL analysis runs on every PR targeting `main`.
- Secret scanning runs on every PR targeting `main` via Gitleaks.
- Dependabot opens weekly update PRs for pip and npm dependencies.

## Gating rules

- All steps must pass to merge.
- Require code review for changes to ranking logic and orchestrator schemas.

## CD (final)

- Build and publish container images.
- Deploy to Azure Container Apps.
- Run migrations as a deployment step.
