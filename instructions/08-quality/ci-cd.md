# CI/CD

## Minimal CI pipeline

1. Install dependencies.
2. Format check (Black).
3. Lint (Ruff for Python; add ESLint when frontend lint config is introduced).
4. Type check (mypy for backend, `tsc` for frontend).
5. Run backend unit/integration tests.
6. Build frontend to catch compile-time and bundling failures before deploy.

Recommended commands:
- `black --check .`
- `ruff check .`
- `mypy apps/api`
- `python -m pytest -q`
- `cd apps/web && npm install && npm run typecheck && npm run build`

## Branch and PR checks

- `Quality Checks` workflow runs on every push to any branch.
- The same workflow runs on every PR targeting `main`.

## Security automation

- CodeQL analysis runs on every PR targeting `main` (Python only until the web app is scaffolded).
- Secret scanning runs on every PR targeting `main` via Gitleaks.
- Dependabot opens weekly update PRs for pip and npm dependencies.

## Gating rules

- All steps must pass to merge.
- Require code review for changes to ranking logic and orchestrator schemas.
- Frontend code changes must pass both `npm run typecheck` and `npm run build` in CI.

## ML evaluation and release gates (final)

- Model changes must include an evaluation report from `03-recommender/evaluation.md`.
- Promotion requires all evaluation gates to pass.
- Every promoted model must include a manifest with:
  - `model_version`
  - `dataset_snapshot_id`
  - `feature_schema_version`
  - `git_sha`
  - `run_timestamp_utc`
- Approval requirement for model promotion:
  - one recommender reviewer
  - one backend reviewer
  - in the university team, one person may satisfy both roles when team size requires it.

## Scheduled ML jobs

- Weekly scheduled evaluation job.
- Monthly scheduled retraining job.
- For cost control under USD 10/month, heavy jobs may run on-demand locally and upload artifacts manually.

## CD (final)

- Build and publish container images.
- Deploy to Azure Container Apps using blue-green revisions.
- Run migrations as a deployment step.
- Shift traffic only after green revision checks pass.

Implemented workflow split:
- `Publish Images`: builds and pushes immutable API and web images to ACR after `Quality Checks`
- `Deploy Dev`: updates Container Apps in the dev environment and runs smoke checks
- `Deploy Prod`: approval-gated deployment with migrations and smoke checks
- `Rollback Container Apps`: manually reactivate a known-good revision

Authentication and secret handling:
- GitHub Actions authenticates to Azure via OIDC (`azure/login`)
- Azure credentials are not stored as long-lived passwords in repo
- Environment-specific Azure resource names are supplied through GitHub environment vars
- Runtime secrets remain in Azure Key Vault / GitHub environment secrets

## Pre-deploy local checklist (backend + frontend)

Run these before triggering deployment:

Backend (repo root):
- `python -m pip install -e ".[dev]"`
- `black --check .`
- `ruff check .`
- `mypy apps/api`
- `python -m pytest -q`

Frontend (`apps/web`):
- `npm install`
- `npm run typecheck`
- `npm run build`
