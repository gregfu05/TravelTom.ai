"""Unit tests for seed catalog helpers."""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import scripts.seed_catalog as seed_catalog
from scripts.seed_catalog import _item_type_from_tags


def test_default_dataset_uses_canonical_composite_csv() -> None:
    assert seed_catalog.DEFAULT_DATASET == (
        Path(seed_catalog.REPO_ROOT)
        / "traveltom"
        / "datasets"
        / "composite"
        / "traveltom_clean.csv"
    )


def test_item_type_ignores_generic_hotels_and_travel_bucket() -> None:
    tags = ["Hotels & Travel", "Wine Tours"]
    assert _item_type_from_tags(tags) == "activity"


def test_item_type_detects_actual_hotel_tags() -> None:
    tags = ["Hotels", "Event Planning & Services"]
    assert _item_type_from_tags(tags) == "hotel"


def test_item_type_detects_restaurant_tags() -> None:
    tags = ["Restaurants", "Seafood"]
    assert _item_type_from_tags(tags) == "restaurant"


def test_load_source_dataset_reads_csv(tmp_path: Path) -> None:
    dataset_path = tmp_path / "traveltom_clean.csv"
    source = pd.DataFrame(
        [
            {
                "name": "Test Hotel",
                "city": "Santa Barbara",
                "country": "US",
            }
        ]
    )
    source.to_csv(dataset_path, index=False)

    loaded, source_label = seed_catalog._load_source_dataset(dataset_path)

    assert source_label == str(dataset_path)
    pd.testing.assert_frame_equal(loaded, source)


def test_load_source_dataset_rejects_non_csv(tmp_path: Path) -> None:
    dataset_path = tmp_path / "business_SB_Cleaned.parquet"
    dataset_path.write_text("legacy", encoding="utf-8")

    with pytest.raises(ValueError, match="Only CSV datasets"):
        seed_catalog._load_source_dataset(dataset_path)


def test_main_async_skips_when_dataset_missing(capsys, tmp_path: Path) -> None:
    args = argparse.Namespace(
        dataset=tmp_path / "traveltom_clean.csv",
        batch_size=500,
        min_review_count=10,
        truncate=False,
        dry_run=False,
    )

    asyncio.run(seed_catalog.main_async(args))
    captured = capsys.readouterr().out

    assert "Dataset not found. Skipping catalog_items seed." in captured


def test_main_async_dry_run_with_present_dataset(capsys, tmp_path: Path) -> None:
    dataset_path = tmp_path / "traveltom_clean.csv"
    pd.DataFrame(
        [
            {
                "business_id": "hotel-1",
                "name": "Test Hotel",
                "city": "Santa Barbara",
                "country": "US",
                "review_count": 25,
                "is_open": 1,
                "categories": "Hotels, Travel",
                "entity_type": "hotel",
            }
        ]
    ).to_csv(dataset_path, index=False)

    args = argparse.Namespace(
        dataset=dataset_path,
        batch_size=500,
        min_review_count=10,
        truncate=False,
        dry_run=True,
    )

    asyncio.run(seed_catalog.main_async(args))
    captured = capsys.readouterr().out

    assert f"Dataset: {dataset_path}" in captured
    assert "Dry-run enabled. No database changes made." in captured


def test_prepare_rows_normalizes_nan_metadata_values() -> None:
    df = pd.DataFrame(
        [
            {
                "business_id": "hotel-1",
                "name": "Test Hotel",
                "city": "Santa Barbara",
                "country": "US",
                "stars": 4.5,
                "review_count": 25,
                "entity_type": "hotel",
                "quality_score": float("nan"),
                "stars_norm": float("nan"),
                "review_count_norm": float("nan"),
                "popularity_norm": float("nan"),
                "address": float("nan"),
            }
        ]
    )

    rows = seed_catalog._prepare_rows(df)

    assert len(rows) == 1
    metadata = rows[0]["metadata_json"]
    assert metadata["quality_score"] is None
    assert metadata["stars_norm"] is None
    assert metadata["review_count_norm"] is None
    assert metadata["popularity_norm"] is None
    assert metadata["address"] is None


def test_main_returns_zero_when_dataset_missing(tmp_path: Path, monkeypatch) -> None:
    args = argparse.Namespace(
        dataset=tmp_path / "traveltom_clean.csv",
        batch_size=500,
        min_review_count=10,
        truncate=False,
        dry_run=False,
    )

    monkeypatch.setattr(seed_catalog, "parse_args", lambda: args)

    assert seed_catalog.main() == 0


def test_main_does_not_swallow_non_file_not_found_errors(
    monkeypatch, tmp_path: Path
) -> None:
    args = argparse.Namespace(
        dataset=tmp_path / "traveltom_clean.csv",
        batch_size=500,
        min_review_count=10,
        truncate=False,
        dry_run=False,
    )

    async def _raising_main_async(_args: argparse.Namespace) -> None:
        raise RuntimeError("unexpected error")

    monkeypatch.setattr(seed_catalog, "parse_args", lambda: args)
    monkeypatch.setattr(seed_catalog, "main_async", _raising_main_async)

    with pytest.raises(RuntimeError, match="unexpected error"):
        seed_catalog.main()


def test_cli_entrypoint_exits_zero_when_dataset_missing(tmp_path: Path) -> None:
    dataset_path = tmp_path / "traveltom_clean.csv"
    env = os.environ.copy()
    env.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://traveltom:traveltom@localhost:5432/traveltom",
    )

    process = subprocess.run(
        [
            sys.executable,
            str(Path(seed_catalog.__file__).resolve()),
            "--dataset",
            str(dataset_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert process.returncode == 0
    assert "Dataset not found. Skipping catalog_items seed." in process.stdout
