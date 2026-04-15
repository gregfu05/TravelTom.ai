"""Unit tests for ranker promotion gate checks."""

from __future__ import annotations

from scripts.check_ranker_gates import (
    _coverage_gate_passed,
    _ml_fallback_gate_passed,
    _ranking_gate_passed,
)


def _candidate_metrics() -> dict[str, float | int]:
    return {
        "coverage_at_k_rate": 0.97,
        "candidate_ndcg_at_k": 0.31,
        "candidate_map_at_k": 0.21,
        "ml_queries_with_fallback": 0,
        "ml_total_queries": 120,
    }


def test_fallback_gate_passes_when_no_fallback_queries() -> None:
    assert _ml_fallback_gate_passed(_candidate_metrics()) is True


def test_fallback_gate_blocks_when_any_query_falls_back() -> None:
    metrics = _candidate_metrics()
    metrics["ml_queries_with_fallback"] = 1

    assert _ml_fallback_gate_passed(metrics) is False


def test_fallback_gate_blocks_when_fallback_metric_missing() -> None:
    metrics = _candidate_metrics()
    metrics.pop("ml_queries_with_fallback")

    assert _ml_fallback_gate_passed(metrics) is False


def test_first_model_gates_require_metrics_and_no_fallback() -> None:
    metrics = _candidate_metrics()

    assert _coverage_gate_passed(metrics) is True
    assert _ranking_gate_passed(metrics, baseline=None) is True
    assert _ml_fallback_gate_passed(metrics) is True
