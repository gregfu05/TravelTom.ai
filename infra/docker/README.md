# Local Infra (Docker)

Purpose: local Docker Compose workflows for PostgreSQL + `pgvector` and one-shot
bootstrap jobs.
Ownership: Infra/Ops.

## Files

- `docker-compose.yml`: base stack with `postgres` and a one-shot `migrate` job.
- `docker-compose.seed.yml`: overlay that adds a one-shot `seed` job.
- `Dockerfile`: shared Python utility image for migrations and seeding.
- `initdb/01-enable-pgvector.sql`: enables `pgvector` during first DB bootstrap.

## Environment

The stack expects the repo-root `.env` file to exist and keeps the current local
`DATABASE_URL` workflow unchanged for host-side processes. The compose jobs
override `DATABASE_URL` inside containers to use the compose-network hostname
`postgres`.

Optional compose overrides can be provided via shell environment variables:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_PORT`
- `PGVECTOR_IMAGE`
- `TRAVELTOM_PYTHON_IMAGE`

Defaults match the current local example credentials and port.

## Usage

Start Postgres and automatically apply Alembic migrations:

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

Start Postgres, apply Alembic migrations, and then seed the catalog:

```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml up --build
```

For detached mode, add `-d` to either command.

## Verification

- `postgres` should report `healthy` before `migrate` starts.
- `migrate` should exit with code `0` after `alembic -c apps/api/alembic.ini upgrade head`.
- `seed` should exit with code `0` after `python scripts/seed_catalog.py --truncate`.

Useful follow-up commands:

```bash
docker compose -f infra/docker/docker-compose.yml ps
docker compose -f infra/docker/docker-compose.yml logs migrate
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml logs seed
```

Reset the local database volume when you need a clean bootstrap:

```bash
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.seed.yml down -v
```

See `instructions/07-infra-ops/local-dev.md` for the broader local development
flow.
