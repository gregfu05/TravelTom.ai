#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  deploy-ollama-service.sh <validate|what-if|deploy> [resource-group] [location]

Defaults:
  resource-group: travel-tom-rg
  location:       resource-group location

Optional environment variables:
  OLLAMA_APP_NAME                     (default: travel-tom-ollama)
  OLLAMA_CONTAINER_ENV_NAME           (default: travel-tom-llm-cae)
  OLLAMA_LOG_ANALYTICS_WORKSPACE_NAME (default: travel-tom-llm-law)
  OLLAMA_IMAGE                        (default: ollama/ollama:latest)
  OLLAMA_MODELS                       (default: llama3.1:8b)
  OLLAMA_WORKLOAD_PROFILE_NAME        (default: Consumption)
  OLLAMA_WORKLOAD_PROFILE_TYPE        (default: Consumption)
  OLLAMA_MIN_REPLICAS                 (default: 1)
  OLLAMA_MAX_REPLICAS                 (default: 1)
  OLLAMA_CPU                          (default: 4)
  OLLAMA_MEMORY                       (default: 8Gi)
  OLLAMA_KEEP_ALIVE                   (default: 30m)
  OLLAMA_INGRESS_EXTERNAL             (default: false)

Example:
  OLLAMA_MODELS='llama3.1:8b,qwen2.5:14b' \
  OLLAMA_MIN_REPLICAS=1 \
  OLLAMA_MEMORY=8Gi \
  infra/azure/scripts/deploy-ollama-service.sh deploy travel-tom-rg
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

validate_consumption_resources() {
  local cpu="$1"
  local memory="$2"

  if [[ ! "$memory" =~ ^([0-9]+([.][0-9]+)?)Gi$ ]]; then
    echo "Invalid OLLAMA_MEMORY for Consumption profile: $memory (expected value like 8Gi)" >&2
    exit 1
  fi

  local memory_gi="${BASH_REMATCH[1]}"

  if ! awk -v c="$cpu" -v m="$memory_gi" 'BEGIN {
    # Consumption profile supports CPU in 0.25 steps from 0.25 to 4.0.
    if (c < 0.25 || c > 4.0) exit 1
    q = c * 4.0
    if ((q - int(q)) > 0.000001 || (int(q) - q) > 0.000001) exit 1

    # Supported shapes follow memory == 2 * CPU in Gi.
    expected = c * 2.0
    if ((m - expected) > 0.000001 || (expected - m) > 0.000001) exit 1
    exit 0
  }'; then
    echo "Invalid CPU/Memory for Consumption profile: CPU=$cpu, MEMORY=$memory." >&2
    echo "Use one of Azure Consumption supported pairs (for example 4 CPU with 8Gi)." >&2
    echo "For larger memory, use a different workload profile type." >&2
    exit 1
  fi
}

ACTION="${1:-}"
RESOURCE_GROUP="${2:-travel-tom-rg}"
LOCATION="${3:-}"

if [[ -z "$ACTION" ]]; then
  usage
  exit 1
fi

case "$ACTION" in
  validate|what-if|deploy) ;;
  *)
    echo "Invalid action: $ACTION (expected validate, what-if, or deploy)" >&2
    exit 1
    ;;
esac

require_cmd az

if [[ -z "$LOCATION" ]]; then
  LOCATION="$(az group show --name "$RESOURCE_GROUP" --query location --output tsv)"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TEMPLATE_FILE="$REPO_ROOT/infra/azure/ollama-service.bicep"

OLLAMA_APP_NAME="${OLLAMA_APP_NAME:-travel-tom-ollama}"
OLLAMA_CONTAINER_ENV_NAME="${OLLAMA_CONTAINER_ENV_NAME:-travel-tom-llm-cae}"
OLLAMA_LOG_ANALYTICS_WORKSPACE_NAME="${OLLAMA_LOG_ANALYTICS_WORKSPACE_NAME:-travel-tom-llm-law}"
OLLAMA_IMAGE="${OLLAMA_IMAGE:-ollama/ollama:latest}"
OLLAMA_MODELS="${OLLAMA_MODELS:-llama3.1:8b}"
OLLAMA_WORKLOAD_PROFILE_NAME="${OLLAMA_WORKLOAD_PROFILE_NAME:-Consumption}"
OLLAMA_WORKLOAD_PROFILE_TYPE="${OLLAMA_WORKLOAD_PROFILE_TYPE:-Consumption}"
OLLAMA_MIN_REPLICAS="${OLLAMA_MIN_REPLICAS:-1}"
OLLAMA_MAX_REPLICAS="${OLLAMA_MAX_REPLICAS:-1}"
OLLAMA_CPU="${OLLAMA_CPU:-4}"
OLLAMA_MEMORY="${OLLAMA_MEMORY:-8Gi}"
OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-30m}"
OLLAMA_INGRESS_EXTERNAL="${OLLAMA_INGRESS_EXTERNAL:-false}"

if [[ "$OLLAMA_WORKLOAD_PROFILE_TYPE" == "Consumption" ]]; then
  validate_consumption_resources "$OLLAMA_CPU" "$OLLAMA_MEMORY"
fi

declare -a DEPLOYMENT_ARGS=(
  "--resource-group" "$RESOURCE_GROUP"
  "--template-file" "$TEMPLATE_FILE"
  "--parameters" "location=${LOCATION}"
  "--parameters" "logAnalyticsWorkspaceName=${OLLAMA_LOG_ANALYTICS_WORKSPACE_NAME}"
  "--parameters" "containerEnvironmentName=${OLLAMA_CONTAINER_ENV_NAME}"
  "--parameters" "ollamaAppName=${OLLAMA_APP_NAME}"
  "--parameters" "ollamaImage=${OLLAMA_IMAGE}"
  "--parameters" "ollamaModelsCsv=${OLLAMA_MODELS}"
  "--parameters" "ollamaWorkloadProfileName=${OLLAMA_WORKLOAD_PROFILE_NAME}"
  "--parameters" "ollamaWorkloadProfileType=${OLLAMA_WORKLOAD_PROFILE_TYPE}"
  "--parameters" "ollamaMinReplicas=${OLLAMA_MIN_REPLICAS}"
  "--parameters" "ollamaMaxReplicas=${OLLAMA_MAX_REPLICAS}"
  "--parameters" "ollamaCpu=${OLLAMA_CPU}"
  "--parameters" "ollamaMemory=${OLLAMA_MEMORY}"
  "--parameters" "ollamaKeepAlive=${OLLAMA_KEEP_ALIVE}"
  "--parameters" "ollamaIngressExternal=${OLLAMA_INGRESS_EXTERNAL}"
)

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
