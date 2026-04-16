# Datasets

Purpose: local dataset snapshots and derived artifacts used by legacy and current recommendation workflows.

Ownership: Backend/Data.

## What Lives Here

- `composite/traveltom_clean.csv`
- `business_SB.csv`
- `composite/`: derived dataset stats and supporting artifacts
- legacy Parquet artifacts used by older prototypes and experiments

## Notes

- `composite/traveltom_clean.csv` is the canonical cleaned dataset for active
  seeding workflows.
- Some artifacts support older Santa Barbara sample flows and offline
  experiments only.
- The recommender v3 pipeline documents its current dataset dependency inside
  `recommendor_v3.py` as `traveltom_clean.csv`; keep dataset docs aligned with
  the actual files present in the repo.
- Do not assume every file here is part of the current production path.

## Related Docs

- `../README.md`
- `../../instructions/03-recommender/recommender-overview.md`
