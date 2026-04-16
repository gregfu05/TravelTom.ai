"""Validate ML training manifest integrity and lineage fields."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

REQUIRED_MANIFEST_FIELDS = (
    "model_version",
    "dataset_snapshot_id",
    "feature_schema_version",
    "git_sha",
    "run_timestamp_utc",
    "training_code_version",
)


def main() -> None:
    args = _parse_args()
    manifest = _read_manifest(args.manifest_json)
    errors = validate_manifest(
        manifest=manifest,
        expected_model_version=args.expected_model_version,
        expected_feature_schema_version=args.expected_feature_schema_version,
    )
    if errors:
        for error in errors:
            print(f"manifest validation error: {error}")
        raise SystemExit("Training manifest validation failed.")

    summary = {
        "model_version": manifest["model_version"],
        "dataset_snapshot_id": manifest["dataset_snapshot_id"],
        "feature_schema_version": manifest["feature_schema_version"],
    }
    print(json.dumps(summary, indent=2))


def validate_manifest(
    *,
    manifest: Mapping[str, object],
    expected_model_version: str = "",
    expected_feature_schema_version: str = "",
) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_MANIFEST_FIELDS:
        value = str(manifest.get(field, "")).strip()
        if not value:
            errors.append(f"missing or empty required field: {field}")

    if expected_model_version:
        model_version = str(manifest.get("model_version", "")).strip()
        if model_version != expected_model_version:
            errors.append(
                "model_version mismatch: "
                f"expected '{expected_model_version}', got '{model_version}'"
            )

    if expected_feature_schema_version:
        schema_version = str(manifest.get("feature_schema_version", "")).strip()
        if schema_version != expected_feature_schema_version:
            errors.append(
                "feature_schema_version mismatch: "
                f"expected '{expected_feature_schema_version}', got '{schema_version}'"
            )

    return errors


def _read_manifest(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Manifest JSON root must be an object.")
    return raw


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate ranker training manifest")
    parser.add_argument("--manifest-json", type=Path, required=True)
    parser.add_argument("--expected-model-version", type=str, default="")
    parser.add_argument("--expected-feature-schema-version", type=str, default="")
    return parser.parse_args()


if __name__ == "__main__":
    main()
