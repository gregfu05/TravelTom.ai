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
- Dev-only Azure ML workspace and blob-backed MLOps storage foundation.
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
5. Seed `catalog_items` if the target environment is still empty.
6. Deploy a green revision with the target model version.
7. Run smoke checks and metric gate checks on green, including chat runtime coverage.
8. Shift traffic from blue to green.
9. Keep the previous blue revision available for fast rollback.

GitHub Actions implementation:
- `Publish Images`
- `Deploy Dev`
- `Deploy Prod`
- `Rollback Container Apps`
- `ML Train Dev`
- `ML Evaluate Dev`
- `ML Promote Dev`

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
- Recommendation query: `POST /api/v1/recommendations/query` returns a valid
  `ranking_version` and `results` array.
- Chat runtime: `/api/v1/chat` passes auth-aware greeting, slot-gating,
  recommendation, and repair-turn smoke coverage.
- Frontend routes load without runtime errors:
  - `/`
  - `/planner`
  - `/why-traveltom`
  - `/how-it-works`
  - `/login`
  - `/signup`

Smoke commands:
- `pwsh ./scripts/smoke-api.ps1 -BaseUrl https://<api-url>`
- `pwsh ./scripts/smoke-web.ps1 -BaseUrl https://<web-url>`
- `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl https://<api-url> -Provider ollama -AccessToken <token>`

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
- `TRAVELTOM_ML_RANKER_ARTIFACT_URI`
- `TRAVELTOM_ML_RANKER_PROMOTED_VERSION`
- `TRAVELTOM_ML_RANKER_CACHE_DIR`

Runtime handling notes:

- `DATABASE_URL` is injected through a Container App secret reference rather
  than a plain-value env var.
- Promoted model references remain normal env vars because they identify
  runtime state rather than secret material.

Frontend runtime/build vars:
- `VITE_API_BASE_URL`
- `VITE_APPINSIGHTS_CONNECTION_STRING`

## Rollback

- Roll traffic back to the previous blue revision if smoke checks fail or guardrail alerts trigger.
- Roll back to the previous promoted blob artifact reference in dev, then redeploy
  or update the API Container App revision.
- Disable AI Search integration by switching to pgvector retriever.
- Use `Rollback Container Apps` to reactivate the previous web and API revisions.

Workflow behavior:

- `Deploy Dev` now runs migrations before image rollout and seeds `catalog_items`
  when the target database is still empty.
- `Deploy Dev` and `Deploy Prod` capture the active API and web revisions before
  mutation and reactivate them automatically if the deploy job fails after image update.
- `ML Promote Dev` captures the current promoted-model env values before mutation
  and restores them on failure when possible.

## Dev-first MLOps rollout

- Dev is the proving ground for Azure MLOps changes.
- Do not enable prod MLOps resources or prod model-promotion workflows until:
  - dev Bicep validation and deploy succeed
  - `ML Train Dev` and `ML Evaluate Dev` complete successfully
  - `ML Promote Dev` is verified against the API runtime
  - rollback to the previous promoted model reference is tested
