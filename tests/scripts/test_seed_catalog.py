"""Unit tests for seed catalog item-type classification."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import scripts.seed_catalog as seed_catalog
from scripts.seed_catalog import _item_type_from_tags


def test_item_type_ignores_generic_hotels_and_travel_bucket() -> None:
    tags = ["Hotels & Travel", "Wine Tours"]
    assert _item_type_from_tags(tags) == "activity"


def test_item_type_detects_actual_hotel_tags() -> None:
    tags = ["Hotels", "Event Planning & Services"]
    assert _item_type_from_tags(tags) == "hotel"


def test_item_type_detects_restaurant_tags() -> None:
    tags = ["Restaurants", "Seafood"]
    assert _item_type_from_tags(tags) == "restaurant"


def test_load_source_dataset_copies_raw_when_cleaned_missing(
    tmp_path: Path, monkeypatch
) -> None:
    raw_path = tmp_path / "business_SB.parquet"
    clean_path = tmp_path / "business_SB_Cleaned.parquet"

    source = pd.DataFrame(
        [
            {
                "business_id": "abc",
                "name": "Test Hotel",
                "city": "Santa Barbara",
                "is_open": 1,
                "review_count": 42,
                "stars": 4.5,
            }
        ]
    )
    source.to_parquet(raw_path, index=False)

    monkeypatch.setattr(seed_catalog, "DEFAULT_RAW_DATASET", raw_path)
    monkeypatch.setattr(seed_catalog, "DEFAULT_DATASET", clean_path)

    loaded, source_label = seed_catalog._load_source_dataset(clean_path)

    assert clean_path.exists()
    assert "copied from raw snapshot" in source_label
    pd.testing.assert_frame_equal(loaded, source)
