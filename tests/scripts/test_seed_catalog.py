"""Unit tests for seed catalog item-type classification."""

from __future__ import annotations

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

