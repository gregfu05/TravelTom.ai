# Scripts

Purpose: Data ingestion, seeding, evaluation, and local tooling.
Ownership: Backend/Data.

See `instructions/03-recommender/` and `instructions/07-infra-ops/` for usage.

## Catalog seeding

Load the cleaned Yelp snapshot into `catalog_items`:

```bash
python scripts/seed_catalog.py --truncate
```

The seed script defaults to `traveltom/datasets/business_SB_Cleaned.parquet`.
If the cleaned file is missing, it is generated from
`traveltom/datasets/business_SB.parquet` before seeding.

`item_type` classification uses normalized category tags and avoids treating
generic `Hotels & Travel` buckets as hotels without lodging-specific tags.
When classification logic changes, re-run:

```bash
python scripts/seed_catalog.py --truncate
```

Preview without writing:

```bash
python scripts/seed_catalog.py --dry-run
```
