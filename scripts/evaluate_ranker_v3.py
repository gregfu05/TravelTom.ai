"""Offline evaluation for recommender_v3 rankers.

Compares heuristic baseline vs ML ranker on grouped labels.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from traveltom.recommendor.ml_training_v3 import RankerTrainingDataset
    from traveltom.recommendor.ranking_features_v3 import RankingFeatureContext


def _bootstrap_repo_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    api_root = repo_root / "apps" / "api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))


def main() -> None:
    _bootstrap_repo_paths()
    from traveltom.recommendor.heuristic_ranker_v3 import HeuristicRankerV3
    from traveltom.recommendor.ml_ranker_v3 import (
        ML_FEATURE_COLUMNS,
        LightGBMLTRRankerV3,
        MLRankerConfig,
    )
    from traveltom.recommendor.ranking_eval_v3 import compare_grouped_rankers

    args = _parse_args()

    dataset = _load_dataset(args)
    if dataset.frame.empty:
        raise SystemExit("No evaluation data rows produced.")

    heuristic = HeuristicRankerV3()
    ml_ranker = LightGBMLTRRankerV3(
        config=MLRankerConfig(artifact_path=args.artifact_path)
    )

    eval_rows: list[pd.DataFrame] = []
    ml_fallback_count = 0

    for query_id, group in dataset.frame.groupby("query_id", sort=False):
        context = dataset.query_contexts.get(str(query_id), _empty_context())
        features = group[["business_id", *ML_FEATURE_COLUMNS]].copy()

        heuristic_scored = heuristic.score(features=features, context=context).scored
        heuristic_scores = heuristic_scored[["business_id", "score_final"]].rename(
            columns={"score_final": "score_heuristic"}
        )

        ml_output = ml_ranker.score(features=features, context=context)
        if ml_output.used_fallback:
            ml_fallback_count += 1
        ml_scores = ml_output.scored[["business_id", "score_final"]].rename(
            columns={"score_final": "score_ml"}
        )

        merged = group[["query_id", "business_id", "label"]].merge(
            heuristic_scores,
            on="business_id",
            how="left",
        )
        merged = merged.merge(ml_scores, on="business_id", how="left")
        merged["score_heuristic"] = pd.to_numeric(
            merged["score_heuristic"],
            errors="coerce",
        ).fillna(0.0)
        merged["score_ml"] = pd.to_numeric(merged["score_ml"], errors="coerce").fillna(
            0.0
        )

        eval_rows.append(merged)

    evaluation_frame = pd.concat(eval_rows, ignore_index=True)

    metrics = compare_grouped_rankers(
        frame=evaluation_frame,
        baseline_score_column="score_heuristic",
        candidate_score_column="score_ml",
        k=args.eval_k,
    )
    metrics["ml_queries_with_fallback"] = ml_fallback_count
    metrics["ml_total_queries"] = len(dataset.query_ids)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))


def _load_dataset(args: argparse.Namespace) -> RankerTrainingDataset:
    from traveltom.recommendor.ml_training_v3 import (
        build_training_dataset_from_judgments,
        build_weak_supervision_training_dataset,
        load_judgments_csv,
    )

    if args.judgments_csv is not None:
        judgments = load_judgments_csv(args.judgments_csv)
        return build_training_dataset_from_judgments(
            judgments=judgments,
            catalog=None,
            max_candidates_per_query=args.max_candidates_per_query,
            min_candidates_per_query=args.min_candidates_per_query,
        )

    return build_weak_supervision_training_dataset(
        catalog=None,
        queries=None,
        max_queries=args.max_weak_queries,
        random_seed=args.seed,
        max_candidates_per_query=args.max_candidates_per_query,
        min_candidates_per_query=args.min_candidates_per_query,
    )


def _empty_context() -> RankingFeatureContext:
    from traveltom.recommendor.ranking_features_v3 import RankingFeatureContext

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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate heuristic vs ML ranker v3")
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=Path("traveltom/recommendor/artifacts/ranker_v3_lgbm_ltr.pkl"),
        help="ML ranker artifact path.",
    )
    parser.add_argument(
        "--judgments-csv",
        type=Path,
        default=None,
        help="Optional explicit judgments CSV for evaluation.",
    )
    parser.add_argument(
        "--max-weak-queries",
        type=int,
        default=120,
        help="Query count for weak-supervision eval mode.",
    )
    parser.add_argument(
        "--max-candidates-per-query",
        type=int,
        default=200,
        help="Max candidates retained per query.",
    )
    parser.add_argument(
        "--min-candidates-per-query",
        type=int,
        default=5,
        help="Min candidates to keep a query group.",
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--eval-k", type=int, default=10)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
