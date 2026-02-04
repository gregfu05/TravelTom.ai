# Evaluation

## Offline evaluation harness

- Input: logged sessions with queries and interactions.
- Output: ranking metrics and comparison across versions.

## Metrics

- NDCG@K
- MAP@K
- CTR proxy on holdout sessions
- Coverage: % sessions with at least N results per category

## Holdout creation

- Split by session_id to avoid leakage.
- 80/20 train/holdout for offline evaluation.

## CTR proxy

- Use event logs to approximate relevance:
  - `click` = positive
  - `save` = strong positive
  - `dismiss` = negative
- Convert to graded relevance (0–2).

## Local run

- Load session logs from `events` table.
- Generate candidate sets using retrieval.
- Score with heuristic or ML model.
- Compute metrics and write a report to `reports/eval_YYYYMMDD.md`.

