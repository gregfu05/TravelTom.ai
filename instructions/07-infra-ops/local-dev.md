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
3. Seed catalog: `python scripts/seed_catalog.py`
4. Start backend and frontend.

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
