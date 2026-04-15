# Cleaning Pipeline

Purpose: legacy local data-preparation scripts for Yelp-derived snapshots.

Ownership: Backend/Data.

## What Lives Here

- `cleaning.py`: trims and enriches the raw business snapshot into a cleaned parquet export.
- `data_extract.py`: extraction helper used by the older cleaning path.

## Output

The documented output of this pipeline is `traveltom/datasets/business_SB_Cleaned.parquet`.

## Notes

- This path is useful for understanding the origin of older local datasets.
- It is not the main runtime app boundary, but it remains relevant for local data workflows and historical context.

## Related Docs

- `../README.md`
- `../../scripts/README.md`
