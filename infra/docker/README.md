# Local Infra (Docker)

Purpose: local Docker Compose workflows for the full stack (PostgreSQL +
`pgvector`, migrations, optional seed, backend API, and frontend web app).
Ownership: Infra/Ops.

## Files

- `docker-compose.yml`: base full stack (`postgres`, one-shot `migrate`, `api`, `web`).
- `docker-compose.seed.yml`: optional overlay that adds one-shot `seed` and makes
  `api` wait for it.
- `Dockerfile`: shared Python image for migrations, seeding, and backend runtime.
- `initdb/01-enable-pgvector.sql`: enables `pgvector` during first DB bootstrap.

## Environment

The stack expects the repo-root `.env` file to exist and keeps the current local
`DATABASE_URL` workflow unchanged for host-side processes. The compose jobs
override `DATABASE_URL` inside containers to use compose-network hostnames.

Optional compose overrides can be provided via shell environment variables:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_PORT`
- `PGVECTOR_IMAGE`
- `TRAVELTOM_PYTHON_IMAGE`
- `TRAVELTOM_NODE_IMAGE`
- `API_PORT`
- `WEB_PORT`
- `VITE_API_PROXY_TARGET`

Defaults are set for local development and can be overridden without changing
checked-in compose files.

## Usage

Start the base full stack (Postgres, migrations, API, and web app):

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

Start the full stack and run the optional one-shot seed job before API startup:

```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml up --build
```

For detached mode, add `-d` to either command.

## Verification

- `postgres` should report `healthy` before `migrate` starts.
- `migrate` should exit with code `0` after `alembic -c apps/api/alembic.ini upgrade head`.
- `seed` should exit with code `0` after `python scripts/seed_catalog.py --truncate` (overlay only).
- API health should respond at `http://localhost:8000/api/v1/health` (or your `API_PORT` override).
- Web app should be available at `http://localhost:5173` (or your `WEB_PORT` override).
- The web service proxies `/api/*` to `VITE_API_PROXY_TARGET` (default `http://api:8000` in compose).

Useful follow-up commands:

```bash
docker compose -f infra/docker/docker-compose.yml ps
docker compose -f infra/docker/docker-compose.yml logs migrate
docker compose -f infra/docker/docker-compose.yml logs api
docker compose -f infra/docker/docker-compose.yml logs web
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml logs seed
```

Reset the local database volume when you need a clean bootstrap:

```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml down -v
```

See `instructions/07-infra-ops/local-dev.md` for the broader local development
flow.
