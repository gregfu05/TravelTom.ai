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

Use existing ranking metrics and guardrails as promotion criteria:

- Offline metrics
  - NDCG@10
  - MAP@10
  - CTR proxy on holdout sessions
  - Coverage pass rate (top-k availability constraints)
- Candidate acceptance
  - Candidate must satisfy the baseline-preservation thresholds defined in
    recommender evaluation docs.
  - Candidate must pass coverage gate before any online rollout.
- Reproducibility checks
  - Re-running the same training manifest should produce equivalent metrics.
  - Input ordering must not alter rank output ordering for identical records.
- Release decision output
  - `promote` or `reject` with a signed evaluation summary and gate outcomes.

### Deployment path

Planned deployment progression (future):

1. Local + CI validation
   - Unit/integration tests and offline ranking harness pass.
2. Development environment deployment
   - Deploy model-serving revision in non-production environment.
   - Validate API compatibility with existing recommender interfaces.
3. Staging shadow/canary
   - Run shadow scoring on staging traffic (no user-visible impact).
   - Compare shadow metrics against active baseline.
4. Production canary
   - Route a small traffic slice to new ranker revision.
   - Monitor quality and latency guardrails with automatic rollback triggers.
5. Full promotion
   - Shift traffic fully when canary is stable and guardrails hold.

Rollback path:

- Roll back to previous model version and previous service revision together.
- Keep at least one known-good model version immediately deployable.

### Post-stability work only

The following should happen only after the ranker is stable in production
(quality and reliability consistently meeting gates):

- Automate scheduled retraining with approval workflow.
- Add drift detection alerts (feature drift and relevance drift).
- Introduce auto-candidate generation from retraining triggers.
- Expand A/B experimentation and personalization layers.
- Add cost optimization for Azure compute and endpoint autoscaling.
- Tighten SLO-backed on-call runbooks for model-serving incidents.

Stability criteria to unlock the above:

- No gate breaches for at least two consecutive release cycles.
- No severity-1 ranking regressions in production during that window.
- Online quality proxy does not breach rollback thresholds.

## Open decisions

- Final threshold values for online canary rollback.
- Preferred Azure serving target for ranker inference
  (managed online endpoint vs containerized app endpoint).
- Model explanation payload format for frontend-facing transparency.
