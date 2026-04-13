"""Train TravelTom recommender_v3 ML ranker (LightGBM LTR).

This script supports two label sources:
1) explicit judgments CSV (preferred)
2) weak supervision from current retrieval + feature pipeline (bootstrap)
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from traveltom.recommendor.heuristic_ranker_v3 import HeuristicRankerV3
from traveltom.recommendor.ml_ranker_v3 import (
    ML_FEATURE_COLUMNS,
    MODEL_FAMILY,
    MODEL_SCHEMA_VERSION,
)
from traveltom.recommendor.ml_training_v3 import (
    LABEL_STRATEGY_EXPLICIT,
    RankerTrainingDataset,
    build_feature_matrix,
    build_training_dataset_from_judgments,
    build_weak_supervision_training_dataset,
    load_judgments_csv,
    save_training_dataset,
    split_train_validation_by_query,
)
from traveltom.recommendor.ranking_eval_v3 import compare_grouped_rankers
from traveltom.recommendor.ranking_features_v3 import RankingFeatureContext


def main() -> None:
    args = _parse_args()

    training_data = _load_training_data(args)
    if training_data.frame.empty:
        raise SystemExit("No training data rows produced. Nothing to train.")

    split = split_train_validation_by_query(
        training_data,
        validation_fraction=args.validation_fraction,
        random_seed=args.seed,
    )
    if split.train.frame.empty:
        raise SystemExit("Train split is empty; increase data size.")

    model = _train_lgbm_ranker(
        train=split.train,
        validation=split.validation,
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        num_leaves=args.num_leaves,
        seed=args.seed,
    )

    evaluation = _evaluate_model_against_heuristic(
        model=model,
        validation=split.validation,
        k=args.eval_k,
    )

    artifact_payload = {
        "model": model,
        "feature_columns": list(ML_FEATURE_COLUMNS),
        "model_version": args.model_version or _default_model_version(),
        "model_family": MODEL_FAMILY,
        "schema_version": MODEL_SCHEMA_VERSION,
        "label_strategy": training_data.label_strategy,
        "trained_at": datetime.now(UTC).isoformat(),
        "train_queries": len(split.train.query_ids),
        "validation_queries": len(split.validation.query_ids),
        "evaluation": evaluation,
    }

    args.output_artifact.parent.mkdir(parents=True, exist_ok=True)
    with args.output_artifact.open("wb") as handle:
        pickle.dump(artifact_payload, handle)

    if args.output_metrics_json is not None:
        args.output_metrics_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_metrics_json.write_text(
            json.dumps(evaluation, indent=2), encoding="utf-8"
        )

    if args.output_training_frame is not None:
        save_training_dataset(training_data, args.output_training_frame)

    print("Training complete")
    print(f"artifact: {args.output_artifact}")
    print(json.dumps(evaluation, indent=2))


def _load_training_data(args: argparse.Namespace) -> RankerTrainingDataset:
    if args.judgments_csv is not None:
        judgments = load_judgments_csv(args.judgments_csv)
        dataset = build_training_dataset_from_judgments(
            judgments=judgments,
            catalog=None,
            max_candidates_per_query=args.max_candidates_per_query,
            min_candidates_per_query=args.min_candidates_per_query,
        )
        if dataset.label_strategy != LABEL_STRATEGY_EXPLICIT:
            raise RuntimeError("Expected explicit label strategy for judgments mode")
        return dataset

    return build_weak_supervision_training_dataset(
        catalog=None,
        queries=None,
        max_queries=args.max_weak_queries,
        random_seed=args.seed,
        max_candidates_per_query=args.max_candidates_per_query,
        min_candidates_per_query=args.min_candidates_per_query,
    )


def _train_lgbm_ranker(
    *,
    train: RankerTrainingDataset,
    validation: RankerTrainingDataset,
    n_estimators: int,
    learning_rate: float,
    num_leaves: int,
    seed: int,
) -> Any:
    try:
        from lightgbm import LGBMRanker
    except ImportError as exc:
        raise RuntimeError(
            "LightGBM is not installed. Install with: pip install lightgbm"
        ) from exc

    x_train = build_feature_matrix(train)
    y_train = train.frame["label"].to_numpy(dtype=np.float32)
    group_train = list(train.group_sizes)

    ranker = LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        num_leaves=num_leaves,
        min_data_in_leaf=20,
        random_state=seed,
    )

    fit_kwargs: dict[str, Any] = {
        "X": x_train,
        "y": y_train,
        "group": group_train,
    }

    if not validation.frame.empty and validation.group_sizes:
        x_val = build_feature_matrix(validation)
        y_val = validation.frame["label"].to_numpy(dtype=np.float32)
        fit_kwargs["eval_set"] = [(x_val, y_val)]
        fit_kwargs["eval_group"] = [list(validation.group_sizes)]
        fit_kwargs["eval_at"] = [3, 10]

    ranker.fit(**fit_kwargs)
    return ranker


def _evaluate_model_against_heuristic(
    *,
    model: Any,
    validation: RankerTrainingDataset,
    k: int,
) -> dict[str, float | int | str]:
    if validation.frame.empty:
        return {
            "k": k,
            "query_count": 0,
            "candidate_count": 0,
            "baseline": "heuristic-ranker-v3",
            "candidate": "ml-ranker-v3-lgbm-ltr",
        }

    eval_frame = validation.frame[
        ["query_id", "business_id", "label", *ML_FEATURE_COLUMNS]
    ].copy()
    eval_frame["score_ml"] = np.asarray(
        model.predict(build_feature_matrix(validation)), dtype=np.float32
    )
    eval_frame["score_heuristic"] = _heuristic_scores_for_dataset(validation)

    comparison = compare_grouped_rankers(
        frame=eval_frame,
        baseline_score_column="score_heuristic",
        candidate_score_column="score_ml",
        k=k,
    )
    comparison["baseline"] = "heuristic-ranker-v3"
    comparison["candidate"] = "ml-ranker-v3-lgbm-ltr"
    return comparison


def _heuristic_scores_for_dataset(dataset: RankerTrainingDataset) -> np.ndarray:
    ranker = HeuristicRankerV3()
    scored_blocks: list[pd.DataFrame] = []

    for query_id, group in dataset.frame.groupby("query_id", sort=False):
        context = dataset.query_contexts.get(str(query_id), _empty_context())
        features = group[["business_id", *ML_FEATURE_COLUMNS]].copy()
        scored = ranker.score(features=features, context=context).scored
        scored = scored[["business_id", "score_final"]].rename(
            columns={"score_final": "score_heuristic"}
        )
        scored["query_id"] = str(query_id)
        scored_blocks.append(scored)

    if not scored_blocks:
        return np.zeros(len(dataset.frame), dtype=np.float32)

    merged = dataset.frame[["query_id", "business_id"]].merge(
        pd.concat(scored_blocks, ignore_index=True),
        on=["query_id", "business_id"],
        how="left",
    )
    return (
        pd.to_numeric(merged["score_heuristic"], errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=np.float32)
    )


def _empty_context() -> RankingFeatureContext:
    return RankingFeatureContext(
        normalized_query_text="",
        query_tokens=tuple(),
        category_terms=tuple(),
        entity_types=tuple(),
        requested_item_type=None,
        city=None,
        state=None,
        country=None,
        country_name=None,
        continent=None,
        destination_hint=None,
        require_open=True,
        price_level_min=None,
        price_level_max=None,
    )


def _default_model_version() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train recommender_v3 LightGBM ranker")
    parser.add_argument(
        "--judgments-csv",
        type=Path,
        default=None,
        help="Optional explicit judgment CSV path.",
    )
    parser.add_argument(
        "--output-artifact",
        type=Path,
        default=Path("traveltom/recommendor/artifacts/ranker_v3_lgbm_ltr.pkl"),
        help="Output pickle artifact path.",
    )
    parser.add_argument(
        "--output-metrics-json",
        type=Path,
        default=None,
        help="Optional JSON output path for offline metrics.",
    )
    parser.add_argument(
        "--output-training-frame",
        type=Path,
        default=None,
        help="Optional CSV/Parquet export of training frame.",
    )
    parser.add_argument(
        "--max-weak-queries",
        type=int,
        default=300,
        help="Query count for weak supervision mode.",
    )
    parser.add_argument(
        "--max-candidates-per-query",
        type=int,
        default=250,
        help="Max candidates kept per query group.",
    )
    parser.add_argument(
        "--min-candidates-per-query",
        type=int,
        default=5,
        help="Min candidates required to keep a query group.",
    )
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.2,
        help="Fraction of query groups reserved for validation.",
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--n-estimators", type=int, default=220)
    parser.add_argument("--learning-rate", type=float, default=0.06)
    parser.add_argument("--num-leaves", type=int, default=48)
    parser.add_argument("--eval-k", type=int, default=10)
    parser.add_argument(
        "--model-version",
        type=str,
        default="",
        help="Optional explicit model version string.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
