#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  check-ollama.sh <dev|prod> [resource-group] [ollama-app-name]

Examples:
  infra/azure/scripts/check-ollama.sh dev
  infra/azure/scripts/check-ollama.sh prod traveltom-prod-rg
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ENVIRONMENT="${1:-}"
RESOURCE_GROUP="${2:-}"
OLLAMA_APP_NAME="${3:-}"

if [[ -z "$ENVIRONMENT" ]]; then
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

if [[ -z "$RESOURCE_GROUP" ]]; then
  RESOURCE_GROUP="traveltom-${ENVIRONMENT}-rg"
fi

if [[ -z "$OLLAMA_APP_NAME" ]]; then
  OLLAMA_APP_NAME="traveltom-${ENVIRONMENT}-ollama"
fi

require_cmd az

echo "Checking Ollama app metadata..."
az containerapp show \
  --name "$OLLAMA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "{name:name,latestRevision:properties.latestRevisionName,fqdn:properties.configuration.ingress.fqdn,workloadProfile:properties.workloadProfileName}" \
  --output table

echo
echo "Listing installed models from inside the container..."
az containerapp exec \
  --name "$OLLAMA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --command "ollama list"

echo
echo "Recent Ollama logs:"
az containerapp logs show \
  --name "$OLLAMA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 100
