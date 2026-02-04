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

## First run

1. Start services: `docker compose up -d`
2. Run migrations: `alembic upgrade head`
3. Seed catalog: `python scripts/seed_catalog.py`
4. Start backend and frontend.

