# Remote Ollama Deployment Notes

## Current backend behavior

- Enable remote Ollama with `ORCHESTRATOR_LLM_PROVIDER=ollama`.
- Planner and composer use the structured Ollama client directly.
- `/api/v1/chat` remains backend-owned and deterministic even when Ollama is down.
- Provider stages use:
  - `ORCHESTRATOR_STRUCTURED_TIMEOUT_SECONDS` as the legacy default
  - `ORCHESTRATOR_PLANNER_TIMEOUT_SECONDS` for planner override
  - `ORCHESTRATOR_COMPOSER_TIMEOUT_SECONDS` for composer override
  - `ORCHESTRATOR_PROVIDER_FAILURE_THRESHOLD`
  - `ORCHESTRATOR_PROVIDER_COOLDOWN_SECONDS`

## Required settings

```bash
ORCHESTRATOR_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=https://ollama.example.com
OLLAMA_PLANNING_MODEL=llama3.1:8b
OLLAMA_RESPONSE_MODEL=llama3.1:8b
ORCHESTRATOR_STRUCTURED_TIMEOUT_SECONDS=10
ORCHESTRATOR_PLANNER_TIMEOUT_SECONDS=20
ORCHESTRATOR_COMPOSER_TIMEOUT_SECONDS=20
ORCHESTRATOR_PROVIDER_FAILURE_THRESHOLD=2
ORCHESTRATOR_PROVIDER_COOLDOWN_SECONDS=60
```

## Rollout checklist

1. Deploy Ollama and pre-pull the required models.
2. Put TLS in front of the Ollama endpoint.
3. Restrict ingress to backend network ranges.
4. Update backend env vars and restart the API.
5. Verify:
   - `GET /api/v1/health`
   - `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl https://<api-url> -Provider ollama`
6. Review backend logs for:
   - `provider_stage_succeeded`
   - `provider_stage_failed`
   - `provider_stage_skipped`
   - `planner_execution_failed`
   - `planner_unavailable`

## Failure model

- Planner failure should drop to deterministic clarification/search logic.
- Composer failure should drop to deterministic grounded copy.
- Repeated provider failures should open the stage circuit and avoid repeated
  slow requests until cooldown expires.
