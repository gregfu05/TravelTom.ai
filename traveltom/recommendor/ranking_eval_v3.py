"""Offline grouped ranking evaluation for recommender_v3."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GroupedRankingMetrics:
    ndcg_at_k: float
    mrr_at_k: float
    hit_rate_at_k: float
    mean_label_at_k: float
    query_count: int
    candidate_count: int
    k: int


def ndcg_at_k(labels: np.ndarray, scores: np.ndarray, *, k: int) -> float:
    if labels.size == 0:
        return 0.0

    limit = int(max(1, min(k, labels.size)))
    order = np.argsort(-scores, kind="mergesort")[:limit]
    ranked_labels = labels[order]

    ideal_order = np.argsort(-labels, kind="mergesort")[:limit]
    ideal_labels = labels[ideal_order]

    dcg = _dcg(ranked_labels)
    idcg = _dcg(ideal_labels)
    if idcg <= 0:
        return 0.0
    return float(dcg / idcg)


def mrr_at_k(labels: np.ndarray, scores: np.ndarray, *, k: int) -> float:
    if labels.size == 0:
        return 0.0

    limit = int(max(1, min(k, labels.size)))
    order = np.argsort(-scores, kind="mergesort")[:limit]
    ranked_labels = labels[order]

    positive = np.where(ranked_labels > 0)[0]
    if positive.size == 0:
        return 0.0
    return float(1.0 / (positive[0] + 1.0))


def evaluate_grouped_ranking(
    *,
    frame: pd.DataFrame,
    score_column: str,
    label_column: str = "label",
    query_id_column: str = "query_id",
    k: int = 10,
) -> GroupedRankingMetrics:
    """Compute grouped ranking metrics for a score column."""

    if frame.empty:
        return GroupedRankingMetrics(
            ndcg_at_k=0.0,
            mrr_at_k=0.0,
            hit_rate_at_k=0.0,
            mean_label_at_k=0.0,
            query_count=0,
            candidate_count=0,
            k=k,
        )

    required = {query_id_column, label_column, score_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"frame missing required columns: {sorted(missing)}")

    grouped = frame.groupby(query_id_column, sort=True)
    ndcgs: list[float] = []
    mrrs: list[float] = []
    hits: list[float] = []
    topk_mean_labels: list[float] = []

    for _, group in grouped:
        labels = pd.to_numeric(group[label_column], errors="coerce").fillna(0).to_numpy(dtype=np.float32)
        scores = pd.to_numeric(group[score_column], errors="coerce").fillna(0).to_numpy(dtype=np.float32)

        ndcg_value = ndcg_at_k(labels, scores, k=k)
        mrr_value = mrr_at_k(labels, scores, k=k)
        ndcgs.append(ndcg_value)
        mrrs.append(mrr_value)
        hits.append(1.0 if mrr_value > 0 else 0.0)

        limit = int(max(1, min(k, len(group))))
        order = np.argsort(-scores, kind="mergesort")[:limit]
        topk_mean_labels.append(float(np.mean(labels[order])) if len(order) else 0.0)

    return GroupedRankingMetrics(
        ndcg_at_k=float(np.mean(ndcgs)) if ndcgs else 0.0,
        mrr_at_k=float(np.mean(mrrs)) if mrrs else 0.0,
        hit_rate_at_k=float(np.mean(hits)) if hits else 0.0,
        mean_label_at_k=float(np.mean(topk_mean_labels)) if topk_mean_labels else 0.0,
        query_count=int(grouped.ngroups),
        candidate_count=int(len(frame)),
        k=k,
    )


def compare_grouped_rankers(
    *,
    frame: pd.DataFrame,
    baseline_score_column: str,
    candidate_score_column: str,
    label_column: str = "label",
    query_id_column: str = "query_id",
    k: int = 10,
) -> dict[str, float | int]:
    """Compare two rankers over the same grouped dataset."""

    baseline = evaluate_grouped_ranking(
        frame=frame,
        score_column=baseline_score_column,
        label_column=label_column,
        query_id_column=query_id_column,
        k=k,
    )
    candidate = evaluate_grouped_ranking(
        frame=frame,
        score_column=candidate_score_column,
        label_column=label_column,
        query_id_column=query_id_column,
        k=k,
    )

    return {
        "k": k,
        "query_count": baseline.query_count,
        "candidate_count": baseline.candidate_count,
        "baseline_ndcg_at_k": baseline.ndcg_at_k,
        "baseline_mrr_at_k": baseline.mrr_at_k,
        "baseline_hit_rate_at_k": baseline.hit_rate_at_k,
        "baseline_mean_label_at_k": baseline.mean_label_at_k,
        "candidate_ndcg_at_k": candidate.ndcg_at_k,
        "candidate_mrr_at_k": candidate.mrr_at_k,
        "candidate_hit_rate_at_k": candidate.hit_rate_at_k,
        "candidate_mean_label_at_k": candidate.mean_label_at_k,
        "delta_ndcg_at_k": candidate.ndcg_at_k - baseline.ndcg_at_k,
        "delta_mrr_at_k": candidate.mrr_at_k - baseline.mrr_at_k,
        "delta_hit_rate_at_k": candidate.hit_rate_at_k - baseline.hit_rate_at_k,
        "delta_mean_label_at_k": candidate.mean_label_at_k - baseline.mean_label_at_k,
    }


def _dcg(labels: np.ndarray) -> float:
    if labels.size == 0:
        return 0.0
    gains = np.power(2.0, labels.astype(np.float32)) - 1.0
    positions = np.arange(2, labels.size + 2, dtype=np.float32)
    discounts = np.log2(positions)
    return float(np.sum(gains / discounts))


__all__ = [
    "GroupedRankingMetrics",
    "compare_grouped_rankers",
    "evaluate_grouped_ranking",
    "mrr_at_k",
    "ndcg_at_k",
]
