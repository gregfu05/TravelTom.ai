# Migrations (Alembic)

## Workflow

1. Update SQLAlchemy models.
2. Generate migration: `alembic -c apps/api/alembic.ini revision --autogenerate -m "describe change"`.
3. Review and edit the migration file.
4. Apply migration locally: `alembic -c apps/api/alembic.ini upgrade head`.
5. Verify schema matches expectations.

## Conventions

- Naming: `YYYYMMDDHHMM_description` in revision file comment.
- Keep migrations small and reversible.
- Avoid data migrations in schema migrations; use `scripts/` when needed.
- Always include downgrade steps.

## Verification

- Use `alembic -c apps/api/alembic.ini history` to confirm revision order.
- Use `alembic -c apps/api/alembic.ini current` after upgrade.
- Run DB smoke tests that validate critical tables exist.

## Current auth migration note

- The local-auth library migration is expected to reuse the existing `users.password_hash`
  and `auth_sessions` schema.
- No new Alembic revision is required unless the `users` table shape changes beyond
  that existing compatibility surface.
