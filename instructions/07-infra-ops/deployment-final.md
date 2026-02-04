# Deployment (Final)

## Azure components

- Azure Container Apps (or AKS) for backend and frontend.
- Azure Database for PostgreSQL (with pgvector or AI Search depending on stage).
- Azure AI Search for retrieval.
- Azure OpenAI for LLM.
- Azure Event Hub for event streaming.
- Azure Blob Storage for logs and artifacts.
- Azure ML Registry or MLflow for model versioning (final).
- Application Insights for observability.

## Deployment flow

1. Build and push container images.
2. Provision infra via Bicep/Terraform.
3. Run database migrations.
4. Deploy backend and frontend.
5. Configure environment variables and secrets via Key Vault.

## Rollback

- Roll back to previous container image and migration revision.
- Disable AI Search integration by switching to pgvector retriever.
