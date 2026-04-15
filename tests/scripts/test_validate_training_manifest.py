"""Unit tests for training manifest validation."""

from __future__ import annotations

from scripts.validate_training_manifest import validate_manifest


def _manifest() -> dict[str, str]:
    return {
        "model_version": "abc123",
        "dataset_snapshot_id": "snapshot-v1",
        "feature_schema_version": "ranking-features-v3-v1",
        "git_sha": "abc123",
        "run_timestamp_utc": "2026-04-15T00:00:00+00:00",
        "training_code_version": "abc123",
    }


def test_validate_manifest_success() -> None:
    errors = validate_manifest(
        manifest=_manifest(),
        expected_model_version="abc123",
        expected_feature_schema_version="ranking-features-v3-v1",
    )

    assert errors == []


def test_validate_manifest_reports_missing_required_fields() -> None:
    manifest = _manifest()
    del manifest["git_sha"]
    manifest["dataset_snapshot_id"] = ""

    errors = validate_manifest(manifest=manifest)

    assert "missing or empty required field: git_sha" in errors
    assert "missing or empty required field: dataset_snapshot_id" in errors


def test_validate_manifest_reports_model_version_mismatch() -> None:
    errors = validate_manifest(
        manifest=_manifest(),
        expected_model_version="different-version",
    )

    assert any("model_version mismatch" in error for error in errors)


def test_validate_manifest_reports_feature_schema_mismatch() -> None:
    errors = validate_manifest(
        manifest=_manifest(),
        expected_feature_schema_version="ranking-features-v4-v1",
    )

    assert any("feature_schema_version mismatch" in error for error in errors)
