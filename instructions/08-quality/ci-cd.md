# CI/CD

## Minimal CI pipeline

1. Install dependencies.
2. Format check (Black).
3. Lint (Ruff for Python, plus TS linting).
4. Type check (mypy, tsc).
5. Run unit and integration tests.

Recommended commands:
- `black --check .`
- `ruff check .`
- `mypy apps/api`

## Branch and PR checks

- `Quality Checks` workflow runs on every push to any branch.
- The same workflow runs on every PR targeting `main`.

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
