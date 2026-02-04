# Migrations (Alembic)

## Workflow

1. Update SQLAlchemy models.
2. Generate migration: `alembic revision --autogenerate -m "describe change"`.
3. Review and edit the migration file.
4. Apply migration locally: `alembic upgrade head`.
5. Verify schema matches expectations.

## Conventions

- Naming: `YYYYMMDDHHMM_description` in revision file comment.
- Keep migrations small and reversible.
- Avoid data migrations in schema migrations; use `scripts/` when needed.
- Always include downgrade steps.

## Verification

- Use `alembic history` to confirm revision order.
- Use `alembic current` after upgrade.
- Run DB smoke tests that validate critical tables exist.

