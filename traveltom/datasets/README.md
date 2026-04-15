# Datasets

Purpose: local dataset snapshots and derived artifacts used by legacy and current recommendation workflows.

Ownership: Backend/Data.

## What Lives Here

- `cleaned_Yelp_DS.parquet`
- `business_SB.parquet`
- `business_SB_Cleaned.parquet`
- `business_SB.csv`
- `composite/`: derived dataset stats and supporting artifacts

## Notes

- Some artifacts support older Santa Barbara sample flows.
- The recommender v3 pipeline documents its current dataset dependency inside `recommendor_v3.py` as `traveltom_clean.csv`; keep dataset docs aligned with the actual files present in the repo.
- Do not assume every file here is part of the current production path.

## Related Docs

- `../README.md`
- `../../instructions/03-recommender/recommender-overview.md`
