# Evaluation

## Offline evaluation harness

- Input: logged sessions with queries and interactions.
- Output: ranking metrics and comparison across versions.

## Metrics

- NDCG@10
- MAP@10
- CTR proxy on holdout sessions
- Coverage pass rate: % sessions with at least 5 results per requested category and 20 total results

## Holdout creation

- Split by session_id to avoid leakage.
- 80/20 train/holdout for offline evaluation.

## CTR proxy

- Use event logs to approximate relevance:
  - `click` = positive
  - `save` = strong positive
  - `dismiss` = negative
- Convert to graded relevance (0-2).

## Acceptance gates for model promotion

- Coverage gate:
  - At least 95% of holdout sessions must satisfy both coverage thresholds.
- Ranking quality gate:
  - If a production baseline exists, candidate model must keep NDCG@10 and MAP@10 at or above 99% of baseline values.
  - If no production baseline exists (first model), require NDCG@10 >= 0.20 and MAP@10 >= 0.10.
- Post-deploy guardrail:
  - 7-day CTR proxy must not drop by more than 20% versus trailing 28-day baseline.

## Retraining cadence and triggers

- Scheduled retraining cadence: monthly (first Monday, 06:00 UTC).
- Trigger retraining early when any condition is met:
  - Coverage gate fails in two consecutive weekly evaluations.
  - 7-day CTR proxy drops more than 20% versus trailing 28-day baseline for three consecutive days.
  - New interaction volume increases by at least 30% since last training run.

## Required artifacts per training run

- Model artifact with immutable version id.
- Evaluation report with metrics and gate decisions.
- Training manifest containing:
  - `model_version`
  - `dataset_snapshot_id`
  - `feature_schema_version`
  - `git_sha`
  - `run_timestamp_utc`

## Local run

- Load session logs from `events` table.
- Generate candidate sets using retrieval.
- Score with heuristic or ML model.
- Compute metrics and write a report to `reports/eval_YYYYMMDD.md`.
