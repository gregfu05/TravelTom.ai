"""Apply documented offline acceptance gates to ranker evaluation metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    args = _parse_args()
    candidate = _read_json(args.metrics_json)
    baseline = _read_json(args.baseline_metrics_json) if args.baseline_metrics_json else None

    decision = {
        "coverage_gate_passed": _coverage_gate_passed(candidate),
        "ranking_gate_passed": _ranking_gate_passed(candidate, baseline),
        "baseline_mode": "existing-model" if baseline is not None else "first-model",
    }
    decision["promote"] = bool(
        decision["coverage_gate_passed"] and decision["ranking_gate_passed"]
    )

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(decision, indent=2), encoding="utf-8")

    print(json.dumps(decision, indent=2))
    if not decision["promote"]:
        raise SystemExit("Offline gates failed.")


def _coverage_gate_passed(metrics: dict[str, object]) -> bool:
    return float(metrics.get("coverage_at_k_rate", 0.0)) >= 0.95


def _ranking_gate_passed(
    candidate: dict[str, object],
    baseline: dict[str, object] | None,
) -> bool:
    candidate_ndcg = float(candidate.get("candidate_ndcg_at_k", 0.0))
    candidate_map = float(candidate.get("candidate_map_at_k", 0.0))

    if baseline is None:
        return candidate_ndcg >= 0.20 and candidate_map >= 0.10

    baseline_ndcg = float(
        baseline.get("candidate_ndcg_at_k", baseline.get("baseline_ndcg_at_k", 0.0))
    )
    baseline_map = float(
        baseline.get("candidate_map_at_k", baseline.get("baseline_map_at_k", 0.0))
    )
    return candidate_ndcg >= (baseline_ndcg * 0.99) and candidate_map >= (
        baseline_map * 0.99
    )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check offline ranker gates")
    parser.add_argument("--metrics-json", type=Path, required=True)
    parser.add_argument("--baseline-metrics-json", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
