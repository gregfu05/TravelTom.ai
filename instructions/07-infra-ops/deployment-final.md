# Deployment (Final)

## Azure components

- Azure Container Apps for backend and frontend.
- Azure Database for PostgreSQL (pgvector fallback data path).
- Azure AI Search as the primary retrieval backend.
- Azure OpenAI for LLM.
- Azure Event Hub for event streaming.
- Azure Blob Storage for logs and artifacts.
- Azure ML Registry for model versioning.
- Application Insights for observability.

## Budget mode constraints (university project)

- Cloud spend cap: USD 10/month.
- Keep Container Apps on scale-to-zero when idle.
- Default max replicas per service: 1.
- Run AI Search and Event Hub only during demo or validation windows when possible.
- Use pgvector fallback for low-cost local and rollback operation.

## Deployment flow (blue-green)

1. Run pre-deploy validation checks for backend and frontend.
2. Build and push container images.
3. Provision infra via Bicep/Terraform.
4. Run database migrations.
5. Deploy a green revision with the target model version.
6. Run smoke checks and metric gate checks on green.
7. Shift traffic from blue to green.
8. Keep the previous blue revision available for fast rollback.

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

## Rollback

- Roll traffic back to the previous blue revision if smoke checks fail or guardrail alerts trigger.
- Roll back to the previous model version in Azure ML Registry.
- Disable AI Search integration by switching to pgvector retriever.
