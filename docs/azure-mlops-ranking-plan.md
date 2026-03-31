# Azure MLOps Plan for Ranking Model (Future)

## Purpose

Define a future Azure-based MLOps plan for the TravelTom ranking model without
provisioning or implementing Azure resources yet.

## Scope and constraints

- This document is planning-only.
- No infrastructure provisioning or deployment automation is part of this step.
- Existing deterministic ranking behavior remains the active production path.

## Target outcomes

- A repeatable training flow for ranking model iterations.
- Clear model and dataset versioning strategy.
- Explicit offline/online evaluation gates for promotion decisions.
- A staged deployment path from development to production.
- A strict list of work that should happen only after the ranker is stable.

## Planned architecture (future state)

### Training flow

Planned sequence:

1. Data extraction
   - Pull interaction and recommendation outcomes from the event pipeline.
   - Build a training snapshot keyed by `dataset_snapshot_id`.
2. Feature build
   - Recreate ranking features with a pinned `feature_schema_version`.
   - Validate feature completeness and null-rate thresholds before training.
3. Split and train
   - Split by `session_id` to prevent leakage.
   - Train candidate ranking models on Azure ML compute (future).
4. Offline evaluation
   - Run the shared evaluation harness and generate metrics report artifacts.
5. Registration decision
   - Register only models that pass acceptance gates and reproducibility checks.

Training run artifacts (required):

- Trained model artifact.
- Evaluation report.
- Training manifest:
  - `model_version`
  - `dataset_snapshot_id`
  - `feature_schema_version`
  - `git_sha`
  - `run_timestamp_utc`
  - `training_code_version`

### Model and data versioning

Versioning policy (planned):

- Model versions
  - Use immutable semantic model identifiers (for example
    `ranker_ml_v1.2.0+build.<short_sha>`).
  - Store model lineage and metadata in Azure ML Registry (future).
- Dataset snapshots
  - Create immutable, timestamped dataset snapshots in blob-backed storage
    (future), referenced by `dataset_snapshot_id`.
- Feature schema
  - Track feature definitions independently as `feature_schema_version`.
  - Any schema-breaking feature change must require a new model major version.
- Promotion metadata
  - Every promoted model must point to:
    - one exact dataset snapshot
    - one exact feature schema version
    - one exact training code revision

### Evaluation and promotion gates

TBD

### Deployment path

TBD

### Post-stability work only

TBD

## Open decisions

- TBD
