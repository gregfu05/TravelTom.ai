#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  deploy-env.sh <dev|prod> <validate|what-if|deploy> [resource-group]

Required environment variables:
  POSTGRES_ADMIN_PASSWORD
  LOCAL_AUTH_TOKEN_SECRET

Optional environment variables:
  OPENAI_API_KEY
  API_IMAGE
  WEB_IMAGE
  OLLAMA_IMAGE
  OLLAMA_PLANNING_MODEL
  OLLAMA_RESPONSE_MODEL
  OLLAMA_MIN_REPLICAS
  OLLAMA_MAX_REPLICAS
  OLLAMA_CPU
  OLLAMA_MEMORY
  OLLAMA_KEEP_ALIVE
  ENABLE_MLOPS
  PROMOTED_ML_MODEL_ARTIFACT_URI
  PROMOTED_ML_MODEL_VERSION
  ACR_PUBLIC_NETWORK_ACCESS
  KEYVAULT_PUBLIC_NETWORK_ACCESS
  POSTGRES_PUBLIC_NETWORK_ACCESS
  POSTGRES_ALLOW_AZURE_SERVICES_FIREWALL
  MLOPS_STORAGE_PUBLIC_NETWORK_ACCESS
  API_CONTAINER_CPU
  API_CONTAINER_MEMORY
  WEB_CONTAINER_CPU
  WEB_CONTAINER_MEMORY

Examples:
  POSTGRES_ADMIN_PASSWORD='...' LOCAL_AUTH_TOKEN_SECRET='...' \
    infra/azure/scripts/deploy-env.sh dev validate

  POSTGRES_ADMIN_PASSWORD='...' LOCAL_AUTH_TOKEN_SECRET='...' \
    API_IMAGE='myacr.azurecr.io/traveltom-api:abc123' \
    WEB_IMAGE='myacr.azurecr.io/traveltom-web:abc123' \
    infra/azure/scripts/deploy-env.sh dev deploy
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_env() {
  local key="$1"
  if [[ -z "${!key:-}" ]]; then
    echo "Missing required environment variable: $key" >&2
    exit 1
  fi
}

ENVIRONMENT="${1:-}"
ACTION="${2:-}"
RESOURCE_GROUP="${3:-}"

if [[ -z "$ENVIRONMENT" || -z "$ACTION" ]]; then
  usage
  exit 1
fi

case "$ENVIRONMENT" in
  dev|prod) ;;
  *)
    echo "Invalid environment: $ENVIRONMENT (expected dev or prod)" >&2
    exit 1
    ;;
esac

case "$ACTION" in
  validate|what-if|deploy) ;;
  *)
    echo "Invalid action: $ACTION (expected validate, what-if, or deploy)" >&2
    exit 1
    ;;
esac

if [[ -z "$RESOURCE_GROUP" ]]; then
  RESOURCE_GROUP="traveltom-${ENVIRONMENT}-rg"
fi

require_cmd az
require_env POSTGRES_ADMIN_PASSWORD
require_env LOCAL_AUTH_TOKEN_SECRET

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TEMPLATE_FILE="$REPO_ROOT/infra/azure/main.bicep"
PARAM_FILE="$REPO_ROOT/infra/azure/main.${ENVIRONMENT}.bicepparam"

declare -a DEPLOYMENT_ARGS=(
  "--resource-group" "$RESOURCE_GROUP"
  "--template-file" "$TEMPLATE_FILE"
  "--parameters" "$PARAM_FILE"
  "--parameters" "postgresAdminPassword=${POSTGRES_ADMIN_PASSWORD}"
  "--parameters" "localAuthTokenSecret=${LOCAL_AUTH_TOKEN_SECRET}"
)

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "openaiApiKey=${OPENAI_API_KEY}")
fi
if [[ -n "${API_IMAGE:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "apiImage=${API_IMAGE}")
fi
if [[ -n "${WEB_IMAGE:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "webImage=${WEB_IMAGE}")
fi
if [[ -n "${OLLAMA_IMAGE:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaImage=${OLLAMA_IMAGE}")
fi
if [[ -n "${OLLAMA_PLANNING_MODEL:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaPlanningModel=${OLLAMA_PLANNING_MODEL}")
fi
if [[ -n "${OLLAMA_RESPONSE_MODEL:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaResponseModel=${OLLAMA_RESPONSE_MODEL}")
fi
if [[ -n "${OLLAMA_MIN_REPLICAS:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaMinReplicas=${OLLAMA_MIN_REPLICAS}")
fi
if [[ -n "${OLLAMA_MAX_REPLICAS:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaMaxReplicas=${OLLAMA_MAX_REPLICAS}")
fi
if [[ -n "${OLLAMA_CPU:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaCpu=${OLLAMA_CPU}")
fi
if [[ -n "${OLLAMA_MEMORY:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaMemory=${OLLAMA_MEMORY}")
fi
if [[ -n "${OLLAMA_KEEP_ALIVE:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "ollamaKeepAlive=${OLLAMA_KEEP_ALIVE}")
fi
if [[ -n "${ENABLE_MLOPS:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "enableMlops=${ENABLE_MLOPS}")
fi
if [[ -n "${PROMOTED_ML_MODEL_ARTIFACT_URI:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "promotedMlModelArtifactUri=${PROMOTED_ML_MODEL_ARTIFACT_URI}")
fi
if [[ -n "${PROMOTED_ML_MODEL_VERSION:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "promotedMlModelVersion=${PROMOTED_ML_MODEL_VERSION}")
fi
if [[ -n "${ACR_PUBLIC_NETWORK_ACCESS:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "acrPublicNetworkAccess=${ACR_PUBLIC_NETWORK_ACCESS}")
fi
if [[ -n "${KEYVAULT_PUBLIC_NETWORK_ACCESS:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "keyVaultPublicNetworkAccess=${KEYVAULT_PUBLIC_NETWORK_ACCESS}")
fi
if [[ -n "${POSTGRES_PUBLIC_NETWORK_ACCESS:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "postgresPublicNetworkAccess=${POSTGRES_PUBLIC_NETWORK_ACCESS}")
fi
if [[ -n "${POSTGRES_ALLOW_AZURE_SERVICES_FIREWALL:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "postgresAllowAzureServicesFirewall=${POSTGRES_ALLOW_AZURE_SERVICES_FIREWALL}")
fi
if [[ -n "${MLOPS_STORAGE_PUBLIC_NETWORK_ACCESS:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "mlopsStoragePublicNetworkAccess=${MLOPS_STORAGE_PUBLIC_NETWORK_ACCESS}")
fi
if [[ -n "${API_CONTAINER_CPU:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "apiContainerCpu=${API_CONTAINER_CPU}")
fi
if [[ -n "${API_CONTAINER_MEMORY:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "apiContainerMemory=${API_CONTAINER_MEMORY}")
fi
if [[ -n "${WEB_CONTAINER_CPU:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "webContainerCpu=${WEB_CONTAINER_CPU}")
fi
if [[ -n "${WEB_CONTAINER_MEMORY:-}" ]]; then
  DEPLOYMENT_ARGS+=("--parameters" "webContainerMemory=${WEB_CONTAINER_MEMORY}")
fi

case "$ACTION" in
  validate)
    az deployment group validate "${DEPLOYMENT_ARGS[@]}"
    ;;
  what-if)
    az deployment group what-if "${DEPLOYMENT_ARGS[@]}"
    ;;
  deploy)
    az deployment group create "${DEPLOYMENT_ARGS[@]}"
    ;;
esac
