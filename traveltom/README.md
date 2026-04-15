# Legacy TravelTom Package

Purpose: experiments, historical data-prep code, and recommender pipeline modules that predate the current `apps/` runtime boundaries.

Ownership: Backend/Data.

## How To Read This Folder

- Treat `apps/` as the primary runtime surface.
- Treat this package as legacy-but-still-referenced code.
- Some runtime behavior still imports modules from here, especially the recommender v3 pipeline and older dataset tooling.

## What Lives Here

- `recommendor/`: deterministic ranker pipeline and historical recommender versions.
- `cleaning/`: scripts for preparing legacy Yelp-derived datasets.
- `datasets/`: local dataset snapshots and derived artifacts.
- `prototype_cleaning/`: earlier cleaning experiments kept for reference.
- `evaluation/`, `tuning/`, `models/`, `utils/`: supporting or reserved experiment areas.

## Active vs Historical

- Active in current runtime:
  - `recommendor/recommendor_v3.py`
- Historical or reference-oriented:
  - `recommendor/recommendor_v1.py`
  - `recommendor/recommendor_v2.py`
  - older data-prep paths tied to Santa Barbara/Yelp snapshots

## Working Rules

- Do not move code from here into `apps/` as part of unrelated changes.
- If you need to change a runtime dependency that still points here, document the coupling explicitly.
- Keep README and instruction docs clear about whether a module is runtime-critical or historical reference.

## Related Docs

- `../README.md`
- `../instructions/01-architecture/system-overview.md`
- `../instructions/03-recommender/recommender-overview.md`
