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
- `OPENAI_API_KEY` or `AZURE_OPENAI_KEY`
- `OPENAI_ENDPOINT` (if Azure)
- `APP_ENV=local`

Store these in a local `.env` file (copy from `.env.example`) and do not hard-code them in code.

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
