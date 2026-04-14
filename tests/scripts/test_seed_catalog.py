"""Unit tests for seed catalog helpers."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import pandas as pd
import pytest

import scripts.seed_catalog as seed_catalog
from scripts.seed_catalog import _item_type_from_tags


def test_item_type_ignores_generic_hotels_and_travel_bucket() -> None:
    tags = ["Hotels & Travel", "Wine Tours"]
    assert _item_type_from_tags(tags) == "destination"


def test_item_type_detects_actual_hotel_tags() -> None:
    tags = ["Hotels", "Event Planning & Services"]
    assert _item_type_from_tags(tags) == "hotel"


def test_item_type_detects_flight_tags() -> None:
    tags = ["Airports", "Travel Services"]
    assert _item_type_from_tags(tags) == "flight"


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
        include_closed=False,
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
        include_closed=False,
        truncate=False,
        dry_run=True,
    )

    asyncio.run(seed_catalog.main_async(args))
    captured = capsys.readouterr().out

    assert f"Dataset: {dataset_path}" in captured
    assert "Dry-run enabled. No database changes made." in captured
