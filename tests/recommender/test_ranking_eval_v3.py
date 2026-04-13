"""Tests for offline grouped ranking metrics."""

from __future__ import annotations

import pandas as pd

from traveltom.recommendor.ranking_eval_v3 import (
    compare_grouped_rankers,
    evaluate_grouped_ranking,
)



def test_evaluate_grouped_ranking_metrics() -> None:
    frame = pd.DataFrame(
        [
            {"query_id": "q1", "business_id": "a", "label": 3, "score": 0.9},
            {"query_id": "q1", "business_id": "b", "label": 0, "score": 0.1},
            {"query_id": "q2", "business_id": "c", "label": 2, "score": 0.8},
            {"query_id": "q2", "business_id": "d", "label": 1, "score": 0.7},
        ]
    )

    metrics = evaluate_grouped_ranking(frame=frame, score_column="score", k=2)

    assert metrics.query_count == 2
    assert metrics.candidate_count == 4
    assert metrics.ndcg_at_k > 0
    assert metrics.mrr_at_k > 0
    assert metrics.hit_rate_at_k == 1.0



def test_compare_grouped_rankers_reports_deltas() -> None:
    frame = pd.DataFrame(
        [
            {
                "query_id": "q1",
                "business_id": "a",
                "label": 3,
                "score_heuristic": 0.4,
                "score_ml": 0.9,
            },
            {
                "query_id": "q1",
                "business_id": "b",
                "label": 0,
                "score_heuristic": 0.8,
                "score_ml": 0.1,
            },
            {
                "query_id": "q2",
                "business_id": "c",
                "label": 2,
                "score_heuristic": 0.3,
                "score_ml": 0.7,
            },
            {
                "query_id": "q2",
                "business_id": "d",
                "label": 0,
                "score_heuristic": 0.9,
                "score_ml": 0.2,
            },
        ]
    )

    comparison = compare_grouped_rankers(
        frame=frame,
        baseline_score_column="score_heuristic",
        candidate_score_column="score_ml",
        k=2,
    )

    assert comparison["candidate_ndcg_at_k"] >= comparison["baseline_ndcg_at_k"]
    assert comparison["candidate_mrr_at_k"] >= comparison["baseline_mrr_at_k"]
    assert "delta_ndcg_at_k" in comparison
    assert comparison["query_count"] == 2
