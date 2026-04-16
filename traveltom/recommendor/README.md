# Recommender Pipeline

Purpose: deterministic recommendation retrieval and ranking code used by TravelTom.

Ownership: Backend/Data.

## What Lives Here

- `recommendor_v3.py`: current structured/text retrieval and ranking pipeline over the TravelTom clean dataset.
- `heuristic_ranker_v3.py`: heuristic ranking logic.
- `ranking_features_v3.py`: engineered ranking feature generation.
- `ml_ranker_v3.py` and `ml_training_v3.py`: ML ranker loading and training support.
- `ranking_eval_v3.py`: evaluation helpers.
- `recommendor_v1.py`, `recommendor_v2.py`: older pipeline versions preserved for history and comparison.

## Current Runtime Note

The API runtime currently points its deterministic recommendation tool at
`recommendor_v3.py`, with the shared API runtime adapter normalizing
PostgreSQL-backed `catalog_items` rows into the v3 retrieval/ranking shape.
This is the file to inspect first when recommendation ranking behavior changes.

## Related Docs

- `../README.md`
- `../../instructions/03-recommender/recommender-overview.md`
- `../../instructions/03-recommender/heuristic-ranker-spec.md`
- `../../tests/recommender/`
