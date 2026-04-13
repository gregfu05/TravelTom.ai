# Azure Deployment

This folder contains the Azure infrastructure for TravelTom, including a cloud-hosted Ollama service for the chatbot.

## What Gets Deployed

- Azure Container Registry (ACR)
- Azure Container Apps environment with GPU workload profile (`Consumption-GPU-T4`)
- Container Apps: `api`, `web`, and internal-only `ollama`
- Azure Database for PostgreSQL Flexible Server
- Azure Key Vault
- Log Analytics + Application Insights

## Safe Git Workflow (No Main Risk)

Use a feature branch and open a PR for review.

```bash
git switch main
git pull --ff-only
git switch -c feature/infra-ollama-service
```

Keep commits small and frequent:

```bash
git add <files>
git commit -m "infra: <small scoped change>"
```

## Prerequisites

1. Install Azure CLI and authenticate.

```bash
az login
az account set --subscription <subscription-id>
```

2. Create resource groups (one per environment).

```bash
az group create --name traveltom-dev-rg --location westeurope
az group create --name traveltom-prod-rg --location westeurope
```

3. Export deployment secrets.

```bash
export POSTGRES_ADMIN_PASSWORD='<strong-password>'
export LOCAL_AUTH_TOKEN_SECRET='<random-secret>'
# Optional only if OpenAI provider fallback is needed:
# export OPENAI_API_KEY='<key>'
```

## Validate, Preview, Deploy

Use the helper script to avoid long manual commands:

- `infra/azure/scripts/deploy-env.sh`

### Validate

```bash
infra/azure/scripts/deploy-env.sh dev validate
infra/azure/scripts/deploy-env.sh prod validate
```

### What-if (change preview)

```bash
infra/azure/scripts/deploy-env.sh dev what-if
infra/azure/scripts/deploy-env.sh prod what-if
```

### Deploy

```bash
infra/azure/scripts/deploy-env.sh dev deploy
infra/azure/scripts/deploy-env.sh prod deploy
```

## Build and Push App Images

After infra deploy, push API and web images to the environment ACR.

```bash
ACR_NAME=$(az acr list -g traveltom-dev-rg --query "[0].name" -o tsv)
ACR_LOGIN_SERVER=$(az acr show -n "$ACR_NAME" -g traveltom-dev-rg --query loginServer -o tsv)

az acr login --name "$ACR_NAME"

docker build -f apps/api/Dockerfile -t "$ACR_LOGIN_SERVER/traveltom-api:dev" .
docker push "$ACR_LOGIN_SERVER/traveltom-api:dev"

docker build -f apps/web/Dockerfile -t "$ACR_LOGIN_SERVER/traveltom-web:dev" .
docker push "$ACR_LOGIN_SERVER/traveltom-web:dev"
```

Re-deploy with image overrides:

```bash
API_IMAGE="$ACR_LOGIN_SERVER/traveltom-api:dev" \
WEB_IMAGE="$ACR_LOGIN_SERVER/traveltom-web:dev" \
infra/azure/scripts/deploy-env.sh dev deploy
```

## Verify Ollama and API

Use the verification helper:

- `infra/azure/scripts/check-ollama.sh`

```bash
infra/azure/scripts/check-ollama.sh dev
```

Then verify API health:

```bash
API_FQDN=$(az containerapp show \
  --name traveltom-dev-api \
  --resource-group traveltom-dev-rg \
  --query properties.configuration.ingress.fqdn -o tsv)

curl "https://${API_FQDN}/api/v1/health"
```

## Cost and Latency Tuning

The Ollama deployment now supports environment-tunable settings.

| Parameter | Purpose | Dev Default | Prod Default |
|---|---|---|---|
| `ollamaPlanningModel` | Planning model | `llama3.1:8b` | `llama3.1:8b` |
| `ollamaResponseModel` | Response model | `llama3.1:8b` | `llama3.1:8b` |
| `ollamaMinReplicas` | Warm pods for low latency | `0` | `1` |
| `ollamaMaxReplicas` | Upper bound on scale | `1` | `1` |
| `ollamaCpu` | Container CPU | `4` | `4` |
| `ollamaMemory` | Container memory | `8Gi` | `16Gi` |
| `ollamaKeepAlive` | Keep model loaded in RAM | `10m` | `30m` |

Latency notes:

- `ollamaMinReplicas=1` in prod avoids scale-from-zero cold starts.
- On container startup, both configured Ollama models are pulled automatically.
- `OLLAMA_KEEP_ALIVE` keeps loaded models in memory to reduce repeated load overhead.

## Architecture

```text
Internet
  |
  +---> Web Container App (port 8080, external)
  +---> API Container App (port 8000, external)
            |
            +---> Ollama Container App (port 11434, internal only, GPU)
            +---> PostgreSQL Flexible Server
```

## Required Parameters

| Parameter | Description |
|---|---|
| `environment` | `dev` or `prod` |
| `apiImage` | API container image |
| `webImage` | Web container image |
| `ollamaImage` | Ollama container image |
| `ollamaPlanningModel` | Planning model for Ollama |
| `ollamaResponseModel` | Response model for Ollama |
| `ollamaMinReplicas` | Minimum Ollama replicas |
| `ollamaMaxReplicas` | Maximum Ollama replicas |
| `ollamaCpu` | Ollama CPU cores |
| `ollamaMemory` | Ollama memory |
| `ollamaKeepAlive` | Ollama model keep-alive |
| `postgresAdminLogin` | PostgreSQL admin username |
| `postgresAdminPassword` | PostgreSQL admin password (secure) |
| `corsAllowedOrigins` | API CORS origins |
| `frontendApiBaseUrl` | Public API URL for frontend |
| `localAuthTokenSecret` | Local auth token signing secret |
| `openaiApiKey` | Optional OpenAI API key |

## Operational Notes

- API and web Container Apps receive `AcrPull` role assignments automatically via managed identity.
- Keep `main.dev.bicepparam` and `main.prod.bicepparam` as baseline defaults; override via script env vars when testing alternatives.
- GPU workload availability depends on Azure region. If `Consumption-GPU-T4` is unavailable, choose a supported region.

## Destroy Environment

```bash
az group delete --name traveltom-dev-rg --yes --no-wait
az group delete --name traveltom-prod-rg --yes --no-wait
```
