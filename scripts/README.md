# Scripts

Purpose: seeding, evaluation, smoke checks, and local helper tooling.

Ownership: Backend/Data.

## What Lives Here

- `seed_catalog.py`: loads a cleaned snapshot into `catalog_items`.
- `train_ranker_v3.py`: ranker training entrypoint.
- `evaluate_ranker_v3.py`: evaluation helper for the recommender pipeline.
- `check_ranker_gates.py`: gate/check helper for ranking outputs.
- `smoke-api.ps1`: API smoke verification.
- `smoke-web.ps1`: web smoke verification.

## Common Tasks

### Catalog seeding

Load the cleaned Yelp snapshot into `catalog_items`:

```bash
python scripts/seed_catalog.py --truncate
```

Preview without writing:

```bash
python scripts/seed_catalog.py --dry-run
```

The seed script defaults to `traveltom/datasets/business_SB_Cleaned.parquet`.
If the cleaned file is missing, it is copied from `traveltom/datasets/business_SB.parquet` before seeding.

### Smoke checks

```bash
pwsh ./scripts/smoke-api.ps1 -BaseUrl http://localhost:8000
pwsh ./scripts/smoke-web.ps1 -BaseUrl http://localhost:5173
```

## Notes

- Keep one-off developer helpers here instead of scattering them across runtime folders.
- If a script becomes part of the official delivery workflow, mirror the behavior in `instructions/` or the relevant infra README.

## Related Docs

- `../README.md`
- `../instructions/03-recommender/`
- `../instructions/07-infra-ops/`
