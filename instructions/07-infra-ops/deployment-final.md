# Deployment (Final)

## Azure components in repo

- Bicep entrypoint: `infra/azure/main.bicep`
- Environment parameter files:
  - `infra/azure/main.dev.bicepparam`
  - `infra/azure/main.prod.bicepparam`
- Module folder: `infra/azure/modules/`
- Runtime smoke scripts:
  - `scripts/smoke-api.ps1`
  - `scripts/smoke-web.ps1`

## Azure components

- Azure Container Apps for backend and frontend.
- Azure Database for PostgreSQL (pgvector fallback data path).
- Azure Container Registry for image storage.
- Azure Key Vault for production secrets.
- Azure Monitor + Log Analytics + Application Insights for observability.
- Azure AI Search remains the planned primary retrieval backend for the final stack.
- Azure OpenAI for LLM.
- Azure Event Hub and Azure ML Registry remain deferred runtime-follow-up services.

## Budget mode constraints (university project)

- Cloud spend cap: USD 10/month.
- Keep Container Apps on scale-to-zero when idle.
- Default max replicas per service: 1.
- Run AI Search and Event Hub only during demo or validation windows when possible.
- Use pgvector fallback for low-cost local and rollback operation.

## Deployment flow (blue-green)

1. Run pre-deploy validation checks for backend and frontend.
2. Build and push container images.
3. Provision infra via Bicep.
4. Run database migrations.
5. Deploy a green revision with the target model version.
6. Run smoke checks and metric gate checks on green.
7. Shift traffic from blue to green.
8. Keep the previous blue revision available for fast rollback.

GitHub Actions implementation:
- `Publish Images`
- `Deploy Dev`
- `Deploy Prod`
- `Rollback Container Apps`

## Pre-deploy validation checks

Backend checks (repo root):
- `black --check .`
- `ruff check .`
- `mypy apps/api`
- `python -m pytest -q`

Frontend checks (`apps/web`):
- `npm install`
- `npm run typecheck`
- `npm run build`

Required smoke checks after green deploy:
- API health: `GET /api/v1/health` returns `{"status":"ok"}`.
- Frontend routes load without runtime errors:
  - `/`
  - `/planner`
  - `/why-traveltom`
  - `/how-it-works`

Smoke commands:
- `pwsh ./scripts/smoke-api.ps1 -BaseUrl https://<api-url>`
- `pwsh ./scripts/smoke-web.ps1 -BaseUrl https://<web-url>`

## Runtime configuration

Backend runtime env vars:
- `APP_ENV`
- `DATABASE_URL`
- `CORS_ALLOWED_ORIGINS`
- `APPLICATIONINSIGHTS_CONNECTION_STRING`
- `TELEMETRY_SERVICE_NAME`
- `JSON_LOGS_ENABLED`
- `ORCHESTRATOR_OPENAI_API_KEY`
- `LOCAL_AUTH_TOKEN_SECRET`

Frontend runtime/build vars:
- `VITE_API_BASE_URL`
- `VITE_APPINSIGHTS_CONNECTION_STRING`

## Rollback

- Roll traffic back to the previous blue revision if smoke checks fail or guardrail alerts trigger.
- Roll back to the previous model version in Azure ML Registry.
- Disable AI Search integration by switching to pgvector retriever.
- Use `Rollback Container Apps` to reactivate the previous web and API revisions.
