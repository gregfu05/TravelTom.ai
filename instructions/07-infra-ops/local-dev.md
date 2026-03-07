# Local Development

## Dependencies

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+

## Docker Compose (MVP)

Services:
- API service
- Postgres
- pgvector extension enabled

## Environment variables

- `DATABASE_URL`
- `APP_ENV=local`
- `AUTH_ENABLED=false|true`
- `AUTH_APP_CLIENT_ID` (required when `AUTH_ENABLED=true`)
- `AUTH_TENANT_NAME` (required when `AUTH_ENABLED=true`)
- `AUTH_POLICY_NAME` (required when `AUTH_ENABLED=true`)
- `AUTH_REQUIRED_SCOPES` (default `user_impersonation`)
- `LOCAL_AUTH_TOKEN_SECRET` (required for local signup/login and local bearer validation)
- `LOCAL_AUTH_TOKEN_TTL_SECONDS` (default `604800`)
- `CHAT_RATE_LIMIT` (default `30/minute`)
- `ORCHESTRATOR_LLM_PROVIDER=disabled|ollama|openai`
- `ORCHESTRATOR_LLM_TIMEOUT_SECONDS` (default `20`)
- `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`)
- `OLLAMA_PLANNING_MODEL` (default `llama3.1:8b`)
- `OLLAMA_RESPONSE_MODEL` (default `llama3.1:8b`)
- `OLLAMA_TEMPERATURE` (default `0`)
- `ORCHESTRATOR_OPENAI_BASE_URL` (default `https://api.openai.com/v1`)
- `ORCHESTRATOR_OPENAI_API_KEY` or `OPENAI_API_KEY` (required when provider is `openai`)
- `OPENAI_PLANNING_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_RESPONSE_MODEL` (default `gpt-4.1-mini`)
- `OPENAI_TEMPERATURE` (default `0`)

Store these in a local `.env` file (copy from `.env.example`) and do not hard-code them in code.

To enable local Ollama orchestration:

1. Run Ollama locally and pull a model (for example `ollama pull llama3.1:8b`).
2. Set `ORCHESTRATOR_LLM_PROVIDER=ollama` in `.env`.
3. Restart the API process so cached service dependencies reload.

To enable OpenAI orchestration:

1. Set `ORCHESTRATOR_LLM_PROVIDER=openai` in `.env`.
2. Set `ORCHESTRATOR_OPENAI_API_KEY` (or `OPENAI_API_KEY`).
3. Optionally override model and endpoint values.
4. Restart the API process so cached service dependencies reload.

To enable backend auth locally:

1. Set `AUTH_ENABLED=true` in `.env`.
2. Provide Azure AD B2C values for `AUTH_APP_CLIENT_ID`, `AUTH_TENANT_NAME`, and `AUTH_POLICY_NAME`.
3. Optionally override `AUTH_REQUIRED_SCOPES` and `CHAT_RATE_LIMIT`.
4. Restart the API process so cached auth dependencies reload.

To enable TravelTom local account auth locally:

1. Set `LOCAL_AUTH_TOKEN_SECRET` in `.env`.
2. Optionally override `LOCAL_AUTH_TOKEN_TTL_SECONDS`.
3. Run the latest API migrations so the `users.password_hash` column exists.
4. Restart the API process so cached auth dependencies reload.

## First run

1. Start services: `docker compose up -d`
2. Run migrations: `alembic -c apps/api/alembic.ini upgrade head`
3. Build cleaned snapshot (optional if already present): `python -m traveltom.cleaning.cleaning`
   - If skipped and `business_SB_Cleaned.parquet` is missing, the seed script
     copies `business_SB.parquet` into the cleaned path before seeding.
4. Seed catalog: `python scripts/seed_catalog.py --truncate`
5. Start backend and frontend.

Optional pre-check:
- Preview catalog ingestion without writes: `python scripts/seed_catalog.py --dry-run`

## Troubleshooting

- Alembic path error (`Path doesn't exist: migrations`):
  - Run from repo root with config path:
    `alembic -c apps/api/alembic.ini upgrade head`
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
- Frontend chat shows assistant text but no recommendation cards:
  - Verify `/api/v1/chat` network response contains `recommendations` data.
  - Ensure frontend is running against the intended backend
    (`VITE_API_PROXY_TARGET` or default proxy to `http://localhost:8000`).
  - Configure `apps/web/.env` (from `apps/web/.env.example`) when backend is
    not running on `localhost:8000`.

## Pre-deploy checks (local)

Run from repo root:
- `black --check .`
- `ruff check .`
- `mypy apps/api`
- `python -m pytest -q`

Run from `apps/web`:
- `npm install`
- `npm run typecheck`
- `npm run build`
