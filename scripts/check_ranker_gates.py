"""Apply documented offline acceptance gates to ranker evaluation metrics."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path


def main() -> None:
    args = _parse_args()
    candidate = _read_json(args.metrics_json)
    baseline = (
        _read_json(args.baseline_metrics_json) if args.baseline_metrics_json else None
    )

    fallback_gate_passed = _ml_fallback_gate_passed(candidate)
    decision = {
        "coverage_gate_passed": _coverage_gate_passed(candidate),
        "ranking_gate_passed": _ranking_gate_passed(candidate, baseline),
        "fallback_gate_passed": fallback_gate_passed,
        "ml_queries_with_fallback": _metric_as_int(
            candidate, "ml_queries_with_fallback"
        ),
        "ml_total_queries": _metric_as_int(candidate, "ml_total_queries"),
        "baseline_mode": "existing-model" if baseline is not None else "first-model",
    }
    decision["promote"] = bool(
        decision["coverage_gate_passed"]
        and decision["ranking_gate_passed"]
        and decision["fallback_gate_passed"]
    )

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(decision, indent=2), encoding="utf-8")

    print(json.dumps(decision, indent=2))
    if not decision["promote"]:
        raise SystemExit("Offline gates failed.")


def _coverage_gate_passed(metrics: Mapping[str, object]) -> bool:
    return _metric_as_float(metrics, "coverage_at_k_rate") >= 0.95


def _ranking_gate_passed(
    candidate: Mapping[str, object],
    baseline: Mapping[str, object] | None,
) -> bool:
    candidate_ndcg = _metric_as_float(candidate, "candidate_ndcg_at_k")
    candidate_map = _metric_as_float(candidate, "candidate_map_at_k")

    if baseline is None:
        return candidate_ndcg >= 0.20 and candidate_map >= 0.10

    baseline_ndcg = _metric_as_float(
        baseline,
        "candidate_ndcg_at_k",
        fallback_key="baseline_ndcg_at_k",
    )
    baseline_map = _metric_as_float(
        baseline,
        "candidate_map_at_k",
        fallback_key="baseline_map_at_k",
    )
    return candidate_ndcg >= (baseline_ndcg * 0.99) and candidate_map >= (
        baseline_map * 0.99
    )


def _ml_fallback_gate_passed(metrics: Mapping[str, object]) -> bool:
    if "ml_queries_with_fallback" not in metrics:
        return False
    fallback_queries = _metric_as_int(metrics, "ml_queries_with_fallback")
    return fallback_queries == 0


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_as_int(
    metrics: Mapping[str, object],
    key: str,
    *,
    fallback_key: str | None = None,
) -> int:
    return int(_metric_as_float(metrics, key, fallback_key=fallback_key))


def _metric_as_float(
    metrics: Mapping[str, object],
    key: str,
    *,
    fallback_key: str | None = None,
) -> float:
    value = metrics.get(key)
    if value is None and fallback_key is not None:
        value = metrics.get(fallback_key)
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValueError(f"Expected numeric metric for '{key}', got {type(value).__name__}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check offline ranker gates")
    parser.add_argument("--metrics-json", type=Path, required=True)
    parser.add_argument("--baseline-metrics-json", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
