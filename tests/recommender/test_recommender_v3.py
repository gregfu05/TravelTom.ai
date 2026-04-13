"""Tests for recommender_v3 Step 1 retrieval behavior."""

from __future__ import annotations

import pandas as pd
from app.schemas.tools.recommendations import RecommendationQuery

from traveltom.recommendor import recommendor_v3
from traveltom.recommendor.ml_ranker_v3 import clear_ml_ranker_cache


def _query(
    text: str,
    *,
    max_results: int = 5,
    constraints: dict | None = None,
    filters: dict | None = None,
    ranking_version: str = "heuristic-v1",
) -> RecommendationQuery:
    return RecommendationQuery(
        session_id="sess",
        query=text,
        max_results=max_results,
        constraints=constraints or {},
        filters=filters or {},
        ranking_version=ranking_version,
    )


def _catalog() -> pd.DataFrame:
    rows = [
        {
            "business_id": "h-sb-1",
            "name": "Sunset Inn",
            "city": "Santa Barbara",
            "state": "CA",
            "country": "US",
            "country_name": "United States",
            "continent": "North America",
            "latitude": 34.40,
            "longitude": -119.70,
            "stars": 4.6,
            "review_count": 120,
            "categories": "hotel;beachfront;family",
            "attributes": None,
            "is_open": 1,
            "address": "A St",
            "price_level": 3.0,
            "description": "A beach hotel with family suites.",
            "website": "https://example.com/sunset",
            "phone": None,
            "source": "seed",
            "entity_type": "hotel",
            "popularity": 9.0,
        },
        {
            "business_id": "r-sb-1",
            "name": "La Mesa Seafood",
            "city": "Santa Barbara",
            "state": "CA",
            "country": "US",
            "country_name": "United States",
            "continent": "North America",
            "latitude": 34.41,
            "longitude": -119.69,
            "stars": 4.8,
            "review_count": 210,
            "categories": "restaurant;seafood;bar",
            "attributes": None,
            "is_open": 1,
            "address": "B St",
            "price_level": 2.0,
            "description": "Fresh seafood and late dinner service.",
            "website": "",
            "phone": None,
            "source": "seed",
            "entity_type": "restaurant",
            "popularity": 8.5,
        },
        {
            "business_id": "a-sb-1",
            "name": "Botanical Garden",
            "city": "Santa Barbara",
            "state": "CA",
            "country": "US",
            "country_name": "United States",
            "continent": "North America",
            "latitude": 34.42,
            "longitude": -119.72,
            "stars": 4.5,
            "review_count": 150,
            "categories": "attraction;garden;nature",
            "attributes": None,
            "is_open": 1,
            "address": "C St",
            "price_level": None,
            "description": "Outdoor garden attraction.",
            "website": "",
            "phone": None,
            "source": "seed",
            "entity_type": "attraction",
            "popularity": 8.0,
        },
        {
            "business_id": "r-par-1",
            "name": "Le Bistro",
            "city": "Paris",
            "state": "Ile-de-France",
            "country": "FR",
            "country_name": "France",
            "continent": "Europe",
            "latitude": 48.86,
            "longitude": 2.35,
            "stars": 4.9,
            "review_count": 300,
            "categories": "restaurant;french",
            "attributes": None,
            "is_open": 1,
            "address": "D St",
            "price_level": 4.0,
            "description": "French tasting menu.",
            "website": "",
            "phone": None,
            "source": "seed",
            "entity_type": "restaurant",
            "popularity": 9.5,
        },
        {
            "business_id": "h-ny-closed",
            "name": "Closed Midtown Hotel",
            "city": "New York",
            "state": "NY",
            "country": "US",
            "country_name": "United States",
            "continent": "North America",
            "latitude": 40.75,
            "longitude": -73.99,
            "stars": 4.2,
            "review_count": 90,
            "categories": "hotel;business",
            "attributes": None,
            "is_open": 0,
            "address": "E St",
            "price_level": 2.0,
            "description": "Temporarily closed.",
            "website": "",
            "phone": None,
            "source": "seed",
            "entity_type": "hotel",
            "popularity": 5.0,
        },
    ]
    return pd.DataFrame(rows)


def test_multiword_destination_filter_from_constraints() -> None:
    response = recommendor_v3.recommendation_tool(
        _query("recommend places", constraints={"destination": "Santa Barbara"}),
        catalog=_catalog(),
    )

    assert response.results
    assert all(item.features.get("city") == "Santa Barbara" for item in response.results)


def test_item_type_filter_maps_to_entity_type_hotel() -> None:
    response = recommendor_v3.recommendation_tool(
        _query("good stay options", filters={"item_type": "hotel"}),
        catalog=_catalog(),
    )

    assert response.results
    assert all(item.item_type == "hotel" for item in response.results)
    assert all(item.features.get("entity_type") == "hotel" for item in response.results)


def test_flight_filter_returns_empty_without_flight_entities() -> None:
    response = recommendor_v3.recommendation_tool(
        _query("flights to paris", filters={"item_type": "flight"}),
        catalog=_catalog(),
    )

    assert response.results == []


def test_category_and_text_signals_influence_retrieval() -> None:
    response = recommendor_v3.recommendation_tool(
        _query("seafood restaurant in Santa Barbara", max_results=3),
        catalog=_catalog(),
    )

    assert response.results
    assert response.results[0].features["name"] == "La Mesa Seafood"


def test_price_level_filter_is_best_effort() -> None:
    response = recommendor_v3.recommendation_tool(
        _query(
            "restaurants",
            filters={"item_type": "destination", "price_level_max": 2},
            max_results=10,
        ),
        catalog=_catalog(),
    )

    assert response.results
    for item in response.results:
        price_level = item.features.get("price_level")
        if price_level is not None:
            assert price_level <= 2


def test_response_includes_map_url_and_version() -> None:
    response = recommendor_v3.recommendation_tool(
        _query("hotels in santa barbara", filters={"item_type": "hotel"}),
        catalog=_catalog(),
    )

    assert response.results
    assert response.ranking_version == "recommender-v3:heuristic-ranker-v3"
    assert response.results[0].features["map_url"].startswith(
        "https://www.google.com/maps?q="
    )


def test_ml_mode_falls_back_to_heuristic_when_artifact_missing(
    tmp_path,
    monkeypatch,
) -> None:
    clear_ml_ranker_cache()
    missing_artifact = tmp_path / "missing-ranker.pkl"
    monkeypatch.setenv("TRAVELTOM_ML_RANKER_ARTIFACT_PATH", str(missing_artifact))

    response = recommendor_v3.recommendation_tool(
        _query(
            "seafood restaurant in Santa Barbara",
            ranking_version="ml-ranker-v3-lgbm-ltr",
            max_results=3,
        ),
        catalog=_catalog(),
    )

    assert response.results
    assert "ml-ranker-v3-lgbm-ltr-fallback-heuristic-ranker-v3" in response.ranking_version
