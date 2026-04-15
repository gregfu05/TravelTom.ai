# Local Development

## Dependencies

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+

## Docker Compose (MVP)

Services:
- Postgres
- one-shot Alembic migration job
- optional one-shot catalog seed overlay

## Environment variables

- `DATABASE_URL`
- `APP_ENV=local`
- `AUTH_ENABLED=false|true`
- `AUTH_APP_CLIENT_ID` (reserved for later Azure AD B2C deployment work)
- `AUTH_TENANT_NAME` (reserved for later Azure AD B2C deployment work)
- `AUTH_POLICY_NAME` (reserved for later Azure AD B2C deployment work)
- `AUTH_REQUIRED_SCOPES` (default `user_impersonation`, reserved for later provider integration)
- `LOCAL_AUTH_TOKEN_SECRET` (required for local signup/login and local bearer validation; use at least 32 random bytes)
- `LOCAL_AUTH_TOKEN_TTL_SECONDS` (default `604800`)
- `LOCAL_AUTH_TOKEN_IDLE_TIMEOUT_SECONDS` (default `43200`)
- `CHAT_RATE_LIMIT` (default `30/minute`)
- `CHAT_RATE_LIMIT_ENABLED` (optional; defaults to `false` in local/dev and
  `true` outside local/dev)
- `CORS_ALLOWED_ORIGINS` (space- or comma-separated, default `http://localhost:5173 http://127.0.0.1:5173`)
- `ORCHESTRATOR_LLM_PROVIDER=ollama|openai|disabled`
- `ORCHESTRATOR_LLM_TIMEOUT_SECONDS` (default `20`)
- `ORCHESTRATOR_STRUCTURED_TIMEOUT_SECONDS` (default `20`; legacy shared planner/composer budget)
- `ORCHESTRATOR_PLANNER_TIMEOUT_SECONDS` (optional stage override)
- `ORCHESTRATOR_COMPOSER_TIMEOUT_SECONDS` (optional stage override)
- `ORCHESTRATOR_PROVIDER_FAILURE_THRESHOLD` (default `2`)
- `ORCHESTRATOR_PROVIDER_COOLDOWN_SECONDS` (default `60`)
- `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`)
- `OLLAMA_PLANNING_MODEL` (default `llama3.1:8b`)
- `OLLAMA_RESPONSE_MODEL` (default `llama3.1:8b`)
- `OLLAMA_TEMPERATURE` (default `0`)
- `ORCHESTRATOR_OPENAI_BASE_URL` (default `https://api.openai.com/v1`)
- `ORCHESTRATOR_OPENAI_API_KEY` or `OPENAI_API_KEY` (required when provider is `openai`)
- `OPENAI_PLANNING_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_RESPONSE_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_TEMPERATURE` (default `0`)
- `RECOMMENDER_PRELOAD_ON_STARTUP` (default `true`)

Store these in a local `.env` file (copy from `.env.example`) and do not hard-code them in code.

Local chat runtime default:

- `.env.example`, the checked-in local `.env`, and backend config default to
  `ORCHESTRATOR_LLM_PROVIDER=ollama` so local chat uses provider-assisted
  planning/composition by default.
- Set `ORCHESTRATOR_LLM_PROVIDER=disabled` only when you explicitly want the
  deterministic-only runtime/test path.
- `/api/v1/chat` stays backend-owned in every mode.
- `/api/v1/recommendations/query` is deterministic in every mode.
- The live recommendation runtime reads PostgreSQL `catalog_items`, not
  `RECOMMENDER_DATASET_PATH`.

To use the default local Ollama orchestration:

1. Run Ollama locally and pull a model (for example `ollama pull llama3.1:8b`).
2. Set `ORCHESTRATOR_LLM_PROVIDER=ollama` in `.env`.
3. Optionally raise `ORCHESTRATOR_PLANNER_TIMEOUT_SECONDS` and
   `ORCHESTRATOR_COMPOSER_TIMEOUT_SECONDS` above the shared structured timeout
   if the local model is slow.
4. Restart the API process so cached service dependencies reload.

Local Ollama timeout behavior:

- When `ORCHESTRATOR_LLM_PROVIDER=ollama` in local/dev, TravelTom applies a
  higher effective timeout floor for structured stages so realistic prompts can
  complete on slower local models.
- Planner and composer still honor explicit stage overrides when they are above
  those local floors.
- If chat still falls back frequently, inspect local/dev response headers:
  - `X-TravelTom-Planner-Status`
  - `X-TravelTom-Planner-Used`
  - `X-TravelTom-Composer-Status`
  - `X-TravelTom-Composer-Used`
  - `X-TravelTom-Orchestration-Degraded`
  - `X-TravelTom-Fallback-Reason`

If you are not running Ollama locally, switch `.env`
`ORCHESTRATOR_LLM_PROVIDER=disabled` so chat stays on the deterministic fallback
path instead of failing provider calls.

To enable OpenAI orchestration:

1. Set `ORCHESTRATOR_LLM_PROVIDER=openai` in `.env`.
2. Set `ORCHESTRATOR_OPENAI_API_KEY` (or `OPENAI_API_KEY`).
3. Optionally override model and endpoint values.
4. Restart the API process so cached service dependencies reload.

To enable backend auth locally:

1. Set `AUTH_ENABLED=true` in `.env`.
2. For the current backend scope, use TravelTom local bearer tokens from
   `POST /api/v1/auth/signup` or `POST /api/v1/auth/login`.
3. Optionally override `CHAT_RATE_LIMIT`.
4. Set `CHAT_RATE_LIMIT_ENABLED=true` only when you explicitly want to test
   TravelTom-owned chat throttling in local dev.
5. Restart the API process so cached auth dependencies reload.

To enable TravelTom local account auth locally:

1. Set `LOCAL_AUTH_TOKEN_SECRET` in `.env`.
2. Optionally override `LOCAL_AUTH_TOKEN_TTL_SECONDS`.
3. Optionally override `LOCAL_AUTH_TOKEN_IDLE_TIMEOUT_SECONDS`.
4. Install backend dependencies so `fastapi-users` and its password helpers are available.
5. Run the latest API migrations so the existing `users.password_hash` and `auth_sessions`
   tables exist.
6. Restart the API process so cached auth dependencies reload.

Local auth lifecycle notes:

- The current backend build supports local email/password auth end-to-end.
- Local credential storage/verification is library-backed, but logout and idle timeout
  still depend on persisted `auth_sessions`.
- `POST /api/v1/auth/logout` revokes the current local bearer token.
- Local bearer tokens expire by absolute TTL and by inactivity timeout.
- Azure AD B2C deployment/provider wiring is deferred until later deployment work.

## First run

1. Copy `.env.example` to `.env` and keep `DATABASE_URL` aligned with your local
   Postgres port and credentials.
2. Start local Postgres and automatically apply Alembic migrations:
   `docker compose -f infra/docker/docker-compose.yml up --build`
   - Add `-d` if you want the stack to stay up in the background.
3. Build cleaned snapshot (optional if already present): `python -m traveltom.cleaning.cleaning`
   - If skipped and `business_SB_Cleaned.parquet` is missing, the seed script
     copies `business_SB.parquet` into the cleaned path before seeding.
4. Seed catalog with the compose overlay when you want full local bootstrap:
   `docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml up --build`
   - This waits for Postgres health, runs migrations, then runs
     `python scripts/seed_catalog.py --truncate` once and exits.
   - You can still run the script manually from repo root if you only need to
     reseed an already-running database.
5. Start backend and frontend.

Optional pre-check:
- Preview catalog ingestion without writes: `python scripts/seed_catalog.py --dry-run`
- Smoke the running API:
  - `pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000`
  - `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled`
  - `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email smoke@example.com`

## Troubleshooting

- Alembic path error (`Path doesn't exist: migrations`):
  - Run from repo root with config path:
    `alembic -c apps/api/alembic.ini upgrade head`
- Docker compose migration or seed job cannot connect to Postgres:
  - Verify the `postgres` container is healthy with
    `docker compose -f infra/docker/docker-compose.yml ps`.
  - If you changed local DB credentials or port, keep `.env` `DATABASE_URL` and
    compose overrides (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
    `POSTGRES_PORT`) aligned.
  - If `pgvector` was added after an older local volume was created, reset the
    stack and volume:
    `docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml down -v`
- Mypy duplicate module errors (for example `traveltom` in `build/lib`):
  - Generated build artifacts are excluded by project mypy config.
  - If artifacts were created before pulling latest changes, rerun
    `mypy .` after updating, or remove stale `build/` output.
- Chat returns no recommendations:
  - The recommender reads from PostgreSQL `catalog_items`, not directly from parquet.
  - Seed catalog data and verify row count in `catalog_items`.
  - If seed item-type rules changed, re-seed with truncate so existing rows are
    reclassified: `python scripts/seed_catalog.py --truncate`.
  - The recommender refreshes catalog cache automatically when empty results are detected.
  - Inspect `/api/v1/chat` response `state.constraints`; if fields are empty after
    a message that includes destination/dates/budget text, backend extraction wiring
    is stale and the API process should be restarted with the latest code.
  - If row count is non-zero but chat still returns
    `I do not have strong matches yet...`, verify `/api/v1/recommendations/query`
    directly; if that is empty, restart backend and ensure latest recommender code
    is deployed.
  - Restart API after backend code/config changes so cached dependencies refresh.
  - If provider-assisted chat feels unexpectedly fast or robotic, inspect logs
    for `provider_stage_failed`, `provider_stage_skipped`,
    `provider_stage_degraded`, `planner_execution_failed`,
    `orchestrator_turn_completed`, and `planner_unavailable` to confirm whether
    the runtime is operating deterministically.
  - In local/dev, also inspect `X-TravelTom-*` response headers to confirm
    whether the planner/composer actually ran or a degraded fallback path won.
- Chat returns `429` immediately:
  - Inspect `error.code` first.
  - `rate_limit_exceeded` means TravelTom-owned throttling. Use `Retry-After`,
    `details.retry_after_seconds`, and `X-Trace-ID` to confirm the limiter decision.
  - `provider_rate_limited` means the upstream chat provider is quota-limited.
    Do not lower TravelTom throttling to mask that path.
  - In local/dev, confirm whether `CHAT_RATE_LIMIT_ENABLED` is intentionally on.
- Frontend chat shows assistant text but no recommendation cards:
  - Verify `/api/v1/chat` network response contains `recommendations` data.
  - Ensure frontend is running against the intended backend
    (`VITE_API_PROXY_TARGET` or default proxy to `http://localhost:8000`).
  - Configure `apps/web/.env` (from `apps/web/.env.example`) when backend is
    not running on `localhost:8000`.
- Browser requests fail before reaching the API:
  - If the frontend is not using the Vite dev proxy, set backend
    `CORS_ALLOWED_ORIGINS` to include the frontend origin and restart the API.

## Pre-deploy checks (local)

Run from repo root:
- `black --check .`
- `ruff check .`
- `mypy apps/api`
- `venv\Scripts\python.exe -m pytest tests -q`
- `pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000`
- `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider disabled`
- `pwsh ./scripts/smoke-chat-runtime.ps1 -BaseUrl http://localhost:8000 -Provider ollama -Email smoke@example.com`

Run from `apps/web`:
- `npm install`
- `npm run typecheck`
- `npm run build`
