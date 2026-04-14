# Azure Deployment

This folder contains the Azure infrastructure for TravelTom, including a cloud-hosted Ollama service for the chatbot.

## What Gets Deployed

- Azure Container Registry (ACR)
- Azure Container Apps environment with GPU workload profile (`Consumption-GPU-T4`)
- Container Apps: `api`, `web`, and internal-only `ollama`
- Azure Database for PostgreSQL Flexible Server
- Azure Key Vault
- Log Analytics + Application Insights
- Optional Azure ML workspace + blob storage foundation for dev MLOps

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

2. Create resource groups.

```bash
# Single shared resource group (LLM-only path)
az group create --name travel-tom-rg --location westeurope

# Full-stack path (separate dev/prod groups)
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

## Quick Path: Deploy Ollama As A Service (Single Resource Group)

Use this path when you want only the LLM service in `travel-tom-rg`.

- `infra/azure/scripts/deploy-ollama-service.sh`
- Template: `infra/azure/ollama-service.bicep`

Validate:

```bash
infra/azure/scripts/deploy-ollama-service.sh validate travel-tom-rg
```

Preview:

```bash
infra/azure/scripts/deploy-ollama-service.sh what-if travel-tom-rg
```

Deploy:

```bash
OLLAMA_MODELS='llama3.1:8b,qwen2.5:14b' \
OLLAMA_MIN_REPLICAS=1 \
OLLAMA_MEMORY=8Gi \
OLLAMA_KEEP_ALIVE=30m \
OLLAMA_INGRESS_EXTERNAL=true \
infra/azure/scripts/deploy-ollama-service.sh deploy travel-tom-rg
```

Verify:

```bash
infra/azure/scripts/check-ollama.sh shared
```

If you enable `OLLAMA_INGRESS_EXTERNAL=true`, lock down ingress before production use.
For `Consumption` profile, Azure enforces fixed CPU/memory pairs (for example `4 CPU` with `8Gi`).

## Full Stack: Validate, Preview, Deploy

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

## Dev MLOps Foundation

`main.dev.bicepparam` now enables a dev-only MLOps foundation by default.
This adds:

- Azure ML workspace for dev experimentation and model metadata
- Blob storage containers for dataset snapshots, model artifacts, manifests,
  and evaluation reports
- User-assigned managed identity for future ML jobs
- Blob reader access for the API Container App so promoted ranker artifacts can
  be loaded from private storage

Key parameters:

| Parameter | Purpose |
|---|---|
| `enableMlops` | Enables the Azure ML/storage foundation |
| `mlopsDatasetContainerName` | Dataset snapshot container |
| `mlopsArtifactContainerName` | Trained model artifact container |
| `mlopsManifestContainerName` | Training/promotion manifest container |
| `mlopsEvaluationContainerName` | Offline evaluation report container |
| `promotedMlModelArtifactUri` | Runtime artifact URI injected into the API |
| `promotedMlModelVersion` | Runtime promoted model label injected into the API |
| `apiContainerCpu` | API CPU allocation for initial IaC deploys |
| `apiContainerMemory` | API memory allocation for initial IaC deploys |
| `webContainerCpu` | Web CPU allocation for initial IaC deploys |
| `webContainerMemory` | Web memory allocation for initial IaC deploys |
| `postgresAllowAzureServicesFirewall` | Enables the Azure-services firewall rule for Postgres |

Prod keeps `enableMlops=false` until the dev path is stable.

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
infra/azure/scripts/check-ollama.sh shared
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
| `enableMlops` | Enable Azure ML/storage foundation resources |
| `promotedMlModelArtifactUri` | Blob URL or file URI for the promoted ranker |
| `promotedMlModelVersion` | Promoted ranker version label |
| `apiContainerCpu` | API container CPU |
| `apiContainerMemory` | API container memory |
| `webContainerCpu` | Web container CPU |
| `webContainerMemory` | Web container memory |

## Operational Notes

- API and web Container Apps receive `AcrPull` role assignments automatically via managed identity.
- API runtime now receives `DATABASE_URL` via Container App secret reference instead of a plain env value.
- When `enableMlops=true`, the API Container App receives blob read access to the
  MLOps storage account so it can fetch promoted ranker artifacts at startup.
- Keep `main.dev.bicepparam` and `main.prod.bicepparam` as baseline defaults; override via script env vars when testing alternatives.
- GPU workload availability depends on Azure region. If `Consumption-GPU-T4` is unavailable, choose a supported region.
- Shared Azure resources are tagged with `app`, `environment`, `managedBy`, `owner`, and `stack`.

## Workflow Expectations

- `Deploy Dev` and `Deploy Prod` now:
  - validate required environment variables before mutation
  - capture the currently active revisions before deploy
  - stamp revision suffixes from the image tag
  - run stronger smoke checks after deploy
  - reactivate the previous revisions on failure
- `ML Promote Dev` now validates:
  - the target artifact exists in blob storage
  - the latest gate decision for the model has `promote=true`
  - the previous promoted model config can be restored on failure

## Destroy Environment

```bash
az group delete --name traveltom-dev-rg --yes --no-wait
az group delete --name traveltom-prod-rg --yes --no-wait
```
