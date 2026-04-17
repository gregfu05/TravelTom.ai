# Ticket: Validate Azure deployment readiness and execute a dev-first rollout

## Outcome / Goal

Use the existing Azure infrastructure and workflow assets already in this repo to
complete a controlled dev-first deployment readiness pass for TravelTom, then
bootstrap the dev environment with explicit checks for infra, app runtime, and
dev MLOps.

## Why / Context

The repo already contains substantial Azure IaC and GitHub Actions workflows for
Container Apps, PostgreSQL, Key Vault, observability, rollback, and dev MLOps.
What is still missing is the execution pass that confirms the current `main`
branch is ready to deploy with real environment inputs and an explicit sequence
for validation, bootstrap, smoke tests, and rollback.

This ticket captures that work in repo-native format so deployment does not rely
on chat context or memory.

## In Scope

- Validate the Azure IaC already present under `infra/azure/`
- Confirm deployment prerequisites and missing owner-provided inputs
- Bootstrap the Azure dev environment from the existing Bicep entrypoint
- Build and deploy API and web images through the existing workflow shape
- Run migrations and smoke checks for the first dev rollout
- Validate the dev MLOps foundation and promotion path already present in repo
- Produce a production-readiness gap list after dev validation

## Out of Scope

- Replacing the current Azure architecture with a different hosting model
- Production rollout before dev validation is complete
- Large recommender or orchestrator redesign
- Introducing new infrastructure platforms outside the current Azure path

## Repo Context To Read First

- `instructions/07-infra-ops/deployment-final.md`
- `instructions/07-infra-ops/runbooks.md`
- `instructions/07-infra-ops/observability.md`
- `instructions/08-quality/ci-cd.md`
- `infra/azure/README.md`
- `docs/azure-mlops-ranking-plan.md`

## Relevant Files / Modules

- `infra/azure/main.bicep`: main Azure resource-group deployment entrypoint
- `infra/azure/main.dev.bicepparam`: dev baseline parameters, currently enabling dev MLOps by default
- `infra/azure/main.prod.bicepparam`: prod baseline parameters, currently keeping MLOps disabled
- `infra/azure/modules/`: reusable Azure modules for ACR, PostgreSQL, Container Apps, Key Vault, monitoring, AML workspace, storage, and identities
- `infra/azure/scripts/deploy-env.sh`: validate / what-if / deploy helper for full-stack environments
- `infra/azure/scripts/deploy-ollama-service.sh`: standalone Ollama deployment path
- `.github/workflows/publish-images.yml`: immutable app image publish workflow
- `.github/workflows/deploy-dev.yml`: dev Container App image rollout and smoke checks
- `.github/workflows/deploy-prod.yml`: prod rollout, migrations, and smoke checks
- `.github/workflows/rollback-container-app.yml`: manual revision rollback workflow
- `.github/workflows/ml-train-dev.yml`: dev ML training artifact publication
- `.github/workflows/ml-evaluate-dev.yml`: dev offline evaluation and promotion gates
- `.github/workflows/ml-promote-dev.yml`: dev runtime promotion of a candidate ranker artifact
- `scripts/smoke-api.ps1`: API smoke checks
- `scripts/smoke-web.ps1`: web smoke checks
- `scripts/smoke-chat-runtime.ps1`: auth-aware chat/runtime smoke coverage

## Current Behavior

- The repo already provisions an Azure Container Apps-based stack with:
  - ACR
  - API Container App
  - web Container App
  - internal GPU-backed Ollama Container App
  - PostgreSQL Flexible Server
  - Key Vault
  - Log Analytics and Application Insights
  - optional dev-only Azure ML workspace and blob-backed MLOps storage
- Dev and prod deploy workflows already exist.
- Rollback workflow already exists.
- Dev ML train/evaluate/promote workflows already exist.
- The current `main` branch passed:
  - `venv\Scripts\python.exe -m pytest tests -q`
  - `venv\Scripts\python.exe -m mypy apps/api`
  - `venv\Scripts\python.exe -m ruff check .`
  - `npm run typecheck`
- Local Vite production build is sandbox-sensitive in this environment and can
  fail with `spawn EPERM`, so build verification should be treated as valid only
  when run outside the restrictive sandbox or in CI.
- The dev deploy workflow updates app images and runs smoke checks, but it does
  not run database migrations.
- The Bicep parameter files still contain example image names and example public
  URLs, so real deployment values must come from workflow variables or
  environment overrides.

## Desired Behavior

- Azure dev deployment can be executed end to end using the existing IaC and
  workflow assets with no ambiguous operator decisions.
- Required user-owned inputs are explicitly listed before mutation.
- The first dev bootstrap includes infra validation, infra deploy, migrations,
  app deployment, smoke checks, and rollback verification.
- Dev MLOps resources and workflows are validated only in dev, not promoted to
  prod by default.
- Production is explicitly blocked until dev deployment, dev smoke checks, and
  dev rollback are verified.

## Constraints / Non-negotiables

- Follow the existing Azure architecture already committed in `infra/azure/`.
- Reuse current workflows and scripts before adding new deploy paths.
- Do not hard-code secrets, resource names, URLs, or credentials in code.
- Keep dev as the first deployment target.
- Keep prod MLOps disabled until the dev MLOps path is stable.
- Update docs for any workflow, runtime, or deployment-contract change.
- Keep the work small and reviewable.
- Treat GPU-backed Ollama as an explicit cost/quota risk in all rollout notes.

## Implementation Notes

- Preferred approach: keep `infra/azure/main.bicep` as the source of truth and
  use `infra/azure/scripts/deploy-env.sh` plus the existing GitHub Actions
  workflows rather than inventing parallel deployment logic.
- Existing pattern to mirror: `instructions/07-infra-ops/deployment-final.md`
  and `infra/azure/README.md`.
- Avoid: replacing the IaC, bypassing the existing workflows, or blending dev
  and prod rollout into a single first step.
- If assumptions are required, default to:
  - target environment: `dev`
  - LLM path: Azure-hosted Ollama
  - MLOps scope: enabled in dev only

## Inputs Needed From Owner

### Azure account and environment

- Azure subscription ID
- Azure tenant ID
- target region
- confirmation that the region supports `Consumption-GPU-T4`
- confirmation that the required Azure quotas/providers are available

### Deployment decision inputs

- whether to keep the current Azure Ollama path for dev
- whether dev should reuse the shared Ollama service through `EXTERNAL_OLLAMA_BASE_URL`
- whether dev should keep `enableMlops=true`
- whether prod preparation should happen now or remain blocked until dev passes

### Secrets

- `POSTGRES_ADMIN_PASSWORD`
- `LOCAL_AUTH_TOKEN_SECRET`
- optional `OPENAI_API_KEY`

### GitHub environment secrets

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `DEV_DATABASE_URL`
- optional `DEV_FRONTEND_APPINSIGHTS_CONNECTION_STRING`

### GitHub environment variables for `azure-dev`

- `AZURE_CONTAINER_REGISTRY_NAME`
- `AZURE_RESOURCE_GROUP_DEV`
- `AZURE_CONTAINER_APP_API_DEV`
- `AZURE_CONTAINER_APP_WEB_DEV`
- `DEV_API_BASE_URL`

### GitHub environment variables for dev MLOps

- `AZURE_MLOPS_STORAGE_ACCOUNT_NAME`
- `AZURE_MLOPS_DATASET_CONTAINER`
- `AZURE_MLOPS_ARTIFACT_CONTAINER`
- `AZURE_MLOPS_MANIFEST_CONTAINER`
- `AZURE_MLOPS_EVALUATION_CONTAINER`

### Later prod-only inputs

- `AZURE_RESOURCE_GROUP_PROD`
- `AZURE_CONTAINER_APP_API_PROD`
- `AZURE_CONTAINER_APP_WEB_PROD`
- `PROD_DATABASE_URL`

### Current rollout note

- `travel-tom-rg` matches the standalone Ollama path, not a ready-made full API/web deployment by itself
- the GitHub `Deploy Dev` workflow expects existing API and web Container Apps in whatever resource group is configured through `AZURE_RESOURCE_GROUP_DEV`
- any manual local bootstrap from Apple Silicon must build/push images with `--platform linux/amd64` or Azure Container Apps will reject the image manifest

### App/runtime config to confirm

- real API public base URL
- real frontend public URL(s) for CORS
- shared Ollama base URL if reusing `travel-tom-ollama`
- whether frontend App Insights should be enabled
- whether local-auth remains the Azure dev auth path
- whether the dev database should be seeded on first deploy
- whether a promoted ML artifact already exists or the first dev deploy should
  run with empty promotion variables and heuristic fallback behavior

## Acceptance Criteria

- [ ] The existing Azure IaC validates successfully for dev
- [ ] Required owner-provided secrets, env vars, and config values are explicitly documented
- [ ] The dev environment can be provisioned from the current `infra/azure/main.bicep`
- [ ] The first dev bootstrap includes migrations before runtime acceptance
- [ ] API and web smoke checks are run after deploy
- [ ] Chat/runtime smoke is included in the dev validation pass
- [ ] Rollback procedure is documented and tested for dev
- [ ] Dev MLOps validation path is explicitly limited to dev
- [ ] Production remains blocked pending successful dev validation

## Verification / Tests

- Run: `venv\Scripts\python.exe -m pytest tests -q`
- Run: `venv\Scripts\python.exe -m mypy apps/api`
- Run: `venv\Scripts\python.exe -m ruff check .`
- Run: `cd apps\web && npm run typecheck`
- Run: `infra/azure/scripts/deploy-env.sh dev validate`
- Run: `infra/azure/scripts/deploy-env.sh dev what-if`
- Run after deploy: `pwsh ./scripts/smoke-api.ps1 -BaseUrl https://<api-url>`
- Run after deploy: `pwsh ./scripts/smoke-web.ps1 -BaseUrl https://<web-url>`
- Run after deploy: `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl https://<api-url> -Provider ollama -AccessToken <token>`
- Manually verify: previous Container App revisions can be reactivated and re-smoked

## Docs To Update

- `docs/README.md`

## Definition of Done

- This ticket exists in repo and can be used as the operational handoff artifact
- Required owner-provided inputs are listed in one place
- The current Azure IaC already in the repo is explicitly referenced as the implementation baseline
- Verification commands are included
- Remaining prod blockers are explicit

## Open Questions / Assumptions

- Assumption: the current Azure Container Apps + internal Ollama architecture remains the desired first deployment path
- Assumption: dev MLOps should be validated now, prod MLOps later
- Open question: whether the available Azure region and budget tolerate GPU-backed Ollama for the initial rollout
