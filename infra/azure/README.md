# Azure Deployment

This folder contains the Azure deployment assets for TravelTom.

## Provisioned resources

- Azure Container Registry (Basic SKU)
- Azure Container Apps environment with GPU workload profile (`Consumption-GPU-T4`)
- Azure Container Apps for `api`, `web`, and `ollama`
- Azure Database for PostgreSQL Flexible Server (Burstable B1ms, PostgreSQL 16)
- Azure Key Vault (RBAC-enabled)
- Log Analytics workspace
- Application Insights

## Prerequisites

1. Azure CLI installed and authenticated:

   ```bash
   az login
   az account set --subscription <subscription-id>
   ```

2. Create a resource group per environment:

   ```bash
   az group create --name traveltom-dev-rg --location westeurope
   az group create --name traveltom-prod-rg --location westeurope
   ```

3. Generate secrets per environment (keep these safe, you will need them for every deployment):

   ```bash
   # Dev secrets
   openssl rand -base64 24   # postgresAdminPassword (dev)
   openssl rand -base64 24   # localAuthTokenSecret (dev)

   # Prod secrets (must be different from dev)
   openssl rand -base64 24   # postgresAdminPassword (prod)
   openssl rand -base64 24   # localAuthTokenSecret (prod)
   ```

## Validate Bicep (dry run)

Replace `<ENV>` with `dev` or `prod` and use the matching resource group.

```bash
az deployment group validate \
  --resource-group traveltom-<ENV>-rg \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/main.<ENV>.bicepparam \
  --parameters \
    postgresAdminPassword='<YOUR_PASSWORD>' \
    localAuthTokenSecret='<YOUR_SECRET>'
```

## Preview changes (what-if)

```bash
az deployment group what-if \
  --resource-group traveltom-<ENV>-rg \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/main.<ENV>.bicepparam \
  --parameters \
    postgresAdminPassword='<YOUR_PASSWORD>' \
    localAuthTokenSecret='<YOUR_SECRET>'
```

## Deploy

Each environment is fully isolated in its own resource group.

### Dev

```bash
az deployment group create \
  --resource-group traveltom-dev-rg \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/main.dev.bicepparam \
  --parameters \
    postgresAdminPassword='<DEV_PASSWORD>' \
    localAuthTokenSecret='<DEV_SECRET>'
```

### Prod

```bash
az deployment group create \
  --resource-group traveltom-prod-rg \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/main.prod.bicepparam \
  --parameters \
    postgresAdminPassword='<PROD_PASSWORD>' \
    localAuthTokenSecret='<PROD_SECRET>'
```

## Build and push images

Each environment has its own ACR. After deploying, get the ACR login server from the outputs and push your images. Replace `<ENV>` with `dev` or `prod`.

```bash
# Authenticate Docker to ACR
az acr login --name <acr-name>

# Build and push
docker build -t <acr-login-server>/traveltom-api:<ENV> -f apps/api/Dockerfile .
docker push <acr-login-server>/traveltom-api:<ENV>

docker build -t <acr-login-server>/traveltom-web:<ENV> -f apps/web/Dockerfile .
docker push <acr-login-server>/traveltom-web:<ENV>
```

Then re-deploy with the real image references:

```bash
az deployment group create \
  --resource-group traveltom-<ENV>-rg \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/main.<ENV>.bicepparam \
  --parameters \
    postgresAdminPassword='<YOUR_PASSWORD>' \
    localAuthTokenSecret='<YOUR_SECRET>' \
    apiImage='<acr-login-server>/traveltom-api:<ENV>' \
    webImage='<acr-login-server>/traveltom-web:<ENV>'
```

The Ollama app uses the public `ollama/ollama:latest` image directly.

## Verify deployment

Replace `<ENV>` with `dev` or `prod`.

```bash
# List all container apps
az containerapp list --resource-group traveltom-<ENV>-rg --output table

# Check Ollama logs (model pull progress)
az containerapp logs show \
  --name traveltom-<ENV>-ollama \
  --resource-group traveltom-<ENV>-rg \
  --follow

# Hit the API health endpoint
curl https://<api-url>/api/v1/health
```

## Destroy an environment

Deleting the resource group removes all resources for that environment.

```bash
az group delete --name traveltom-dev-rg --yes --no-wait   # dev
az group delete --name traveltom-prod-rg --yes --no-wait  # prod
```

## Architecture

```
Internet
  |
  +---> Web Container App (port 8080, external)
  +---> API Container App (port 8000, external)
            |
            +---> Ollama Container App (port 11434, internal only, GPU)
            +---> PostgreSQL Flexible Server
```

- The **Ollama** app runs on a GPU workload profile (`Consumption-GPU-T4`) with scale-to-zero.
- On startup it pulls the configured model (default `llama3.1:8b`), which takes ~3-5 minutes on cold start.
- The API connects to Ollama via internal FQDN (not exposed to the internet).
- The API uses `ORCHESTRATOR_LLM_PROVIDER=ollama` with `OLLAMA_BASE_URL` pointing to the Ollama app.

## Required parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `environment` | `dev` or `prod` | — |
| `apiImage` | API container image reference | — |
| `webImage` | Web container image reference | — |
| `ollamaImage` | Ollama container image | — |
| `postgresAdminLogin` | PostgreSQL admin username | — |
| `postgresAdminPassword` | PostgreSQL admin password (secure) | — |
| `corsAllowedOrigins` | Allowed CORS origins for the API | — |
| `frontendApiBaseUrl` | Public API URL for the frontend | — |
| `ollamaPlanningModel` | Ollama planning model | `llama3.1:8b` |
| `ollamaResponseModel` | Ollama response model | `llama3.1:8b` |
| `localAuthTokenSecret` | Secret for local auth tokens | `''` |
| `openaiApiKey` | OpenAI API key (if using OpenAI provider) | `''` |

## Notes

- Replace placeholder image names and passwords in the `.bicepparam` files before use.
- The GitHub Actions workflows are the intended deployment entrypoint after initial bootstrap.
- `frontendApiBaseUrl` should point to the public API endpoint including `/api/v1`.
- GPU availability varies by region. If `Consumption-GPU-T4` is not available in your region, check [Azure Container Apps GPU docs](https://learn.microsoft.com/en-us/azure/container-apps/workload-profiles-overview) for supported regions.
