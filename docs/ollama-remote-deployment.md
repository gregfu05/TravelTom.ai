# Remote Ollama Deployment Notes

This is a short operator guide for running Ollama outside the API host
while keeping backend configuration fully env-driven.

## Current backend behavior

- Ollama config is loaded from backend settings:
  - `ORCHESTRATOR_LLM_PROVIDER=ollama`
  - `OLLAMA_BASE_URL`
  - `OLLAMA_PLANNING_MODEL`
  - `OLLAMA_RESPONSE_MODEL`
  - `OLLAMA_TEMPERATURE`
  - `ORCHESTRATOR_LLM_TIMEOUT_SECONDS`
- The backend normalizes `OLLAMA_BASE_URL` at runtime and supports both:
  - local loopback targets (example `http://127.0.0.1:11434`)
  - remote targets (example `https://ollama.example.com`)
- Startup model discovery uses a bounded health timeout so an unreachable
  remote endpoint does not block boot for long.

## Recommended remote setup

1. Deploy Ollama (Container Apps path in this repo):
   - `OLLAMA_INGRESS_EXTERNAL=true infra/azure/scripts/deploy-ollama-service.sh deploy travel-tom-rg`
   - `infra/azure/scripts/check-ollama.sh shared`
2. Put TLS in front of Ollama (reverse proxy or load balancer).
3. Restrict ingress to backend network ranges only.
4. Pre-pull required models on the Ollama host:
   - `OLLAMA_PLANNING_MODEL`
   - `OLLAMA_RESPONSE_MODEL`
5. Set backend env vars (no code changes needed):

```bash
ORCHESTRATOR_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=https://ollama.example.com
OLLAMA_PLANNING_MODEL=llama3.1:8b
OLLAMA_RESPONSE_MODEL=llama3.1:8b
ORCHESTRATOR_LLM_TIMEOUT_SECONDS=20
```

## Health and observability

- Backend startup logs include Ollama model health-check events:
  - `ollama_model_healthcheck_started`
  - `ollama_model_healthcheck_succeeded`
  - `ollama_model_healthcheck_failed`
- `/api/v1/health` logs provider context and Ollama endpoint mode
  (`local` or `remote`).
- If remote Ollama is intermittently unavailable, chat falls back to configured
  model names after discovery failure and keeps strict request timeout behavior.

## Rollout checklist

1. Deploy remote Ollama and verify model availability (`/api/tags` or `/v1/models`).
2. Update backend env vars for `OLLAMA_BASE_URL` and model names.
3. Restart backend processes.
4. Verify logs show `ollama_model_healthcheck_succeeded`.
5. Call `/api/v1/health` and confirm provider context is logged as expected.
