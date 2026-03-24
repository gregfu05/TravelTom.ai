"""Unit tests for the minimal recommender implementation."""

from __future__ import annotations

import pandas as pd
import pytest
from app.schemas.tools.recommendations import RecommendationQuery

from traveltom.recommendor import recommendor_v1

REQUIRED_COLUMNS = [
    "business_id",
    "name",
    "city",
    "stars",
    "review_count",
    "popularity",
    "cat_Shopping",
    "cat_Restaurants",
    "cat_Bars",
    "cat_Nightlife",
    "is_open",
]


def _query(text: str) -> RecommendationQuery:
    return RecommendationQuery(session_id="test-session", query=text, max_results=5)


@pytest.fixture()
def catalog_df() -> pd.DataFrame:
    """Synthetic catalog to keep tests independent from the real dataset."""

    return pd.DataFrame(
        [
            # Shopping top pick
            {
                "business_id": "shop-top",
                "name": "Top Shop",
                "city": "Testville",
                "stars": 4.9,
                "review_count": 200,
                "popularity": 0.8,
                "cat_Shopping": True,
                "cat_Restaurants": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            # Restaurant top pick
            {
                "business_id": "rest-top",
                "name": "Top Restaurant",
                "city": "Testville",
                "stars": 4.9,
                "review_count": 500,
                "popularity": 0.9,
                "cat_Shopping": False,
                "cat_Restaurants": True,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            # Bars / nightlife
            {
                "business_id": "bar-top",
                "name": "Top Bar",
                "city": "Testville",
                "stars": 4.8,
                "review_count": 300,
                "popularity": 0.7,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Bars": True,
                "cat_Nightlife": True,
                "is_open": 1,
            },
            {
                "business_id": "nightlife-2",
                "name": "Nightlife Two",
                "city": "Testville",
                "stars": 4.6,
                "review_count": 250,
                "popularity": 0.65,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Bars": True,
                "cat_Nightlife": True,
                "is_open": 1,
            },
            # Fallback with highest rating
            {
                "business_id": "overall-top",
                "name": "Overall Top",
                "city": "Testville",
                "stars": 5.0,
                "review_count": 100,
                "popularity": 0.6,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
        ]
    )


def test_shop_returns_top_shopping_business(catalog_df: pd.DataFrame) -> None:
    response = recommendor_v1.recommendation_tool(
        _query("find me a shop"), catalog=catalog_df
    )
    assert response.results, "Expected a recommendation for shopping intent"
    top = response.results[0]

    assert top.item_id == "shop-top"
    assert top.rank == 1


def test_restaurant_returns_top_restaurant_business(
    catalog_df: pd.DataFrame,
) -> None:
    response = recommendor_v1.recommendation_tool(
        _query("restaurant please"), catalog=catalog_df
    )
    assert response.results, "Expected a recommendation for restaurant intent"
    top = response.results[0]

    assert top.item_id == "rest-top"
    assert top.rank == 1


def test_unknown_request_returns_top_overall_business(
    catalog_df: pd.DataFrame,
) -> None:
    response = recommendor_v1.recommendation_tool(
        _query("surprise me"), catalog=catalog_df
    )
    assert response.results, "Expected fallback to overall catalog"
    assert response.results[0].item_id == "rest-top"
    assert response.results[0].rank == 1


def test_tie_breaking_prefers_review_count_then_popularity() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "a",
                "name": "Alpha",
                "city": "Testville",
                "stars": 5.0,
                "review_count": 10,
                "popularity": 0.5,
                "cat_Shopping": True,
                "cat_Restaurants": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            {
                "business_id": "b",
                "name": "Bravo",
                "city": "Testville",
                "stars": 5.0,
                "review_count": 15,
                "popularity": 0.2,
                "cat_Shopping": True,
                "cat_Restaurants": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            {
                "business_id": "c",
                "name": "Charlie",
                "city": "Testville",
                "stars": 5.0,
                "review_count": 15,
                "popularity": 0.9,
                "cat_Shopping": True,
                "cat_Restaurants": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
        ]
    )

    response = recommendor_v1.recommendation_tool(
        _query("shop for gifts"), catalog=catalog
    )
    assert response.results, "Expected a recommendation from tie-breaking catalog"
    top = response.results[0]

    assert top.item_id == "c"


def test_missing_dataset_returns_empty_results() -> None:
    empty_catalog = pd.DataFrame(columns=REQUIRED_COLUMNS)
    response = recommendor_v1.recommendation_tool(
        _query("anything"), catalog=empty_catalog
    )

    assert response.results == []


def test_composite_scoring_changes_ranking() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "high-stars-low-reviews",
                "name": "Shiny Place",
                "city": "Testville",
                "stars": 5.0,
                "review_count": 10,
                "popularity": 0.1,
                "cat_Restaurants": True,
                "cat_Shopping": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            {
                "business_id": "lower-stars-many-reviews",
                "name": "Beloved Spot",
                "city": "Testville",
                "stars": 4.7,
                "review_count": 1000,
                "popularity": 0.9,
                "cat_Restaurants": True,
                "cat_Shopping": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
        ]
    )

    response = recommendor_v1.recommendation_tool(_query("restaurant"), catalog=catalog)

    assert response.results[0].item_id == "lower-stars-many-reviews"


def test_max_results_respected(catalog_df: pd.DataFrame) -> None:
    query = RecommendationQuery(
        session_id="test-session",
        query="nightlife",
        max_results=2,
    )
    response = recommendor_v1.recommendation_tool(query, catalog=catalog_df)

    assert len(response.results) == 2
    assert response.results[0].rank == 1
    assert response.results[1].rank == 2


def test_category_filter_fallbacks_to_all_when_empty() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "only-one",
                "name": "Only One",
                "city": "Testville",
                "stars": 4.5,
                "review_count": 50,
                "popularity": 0.4,
                "cat_Restaurants": False,
                "cat_Shopping": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            }
        ]
    )

    response = recommendor_v1.recommendation_tool(_query("restaurant"), catalog=catalog)

    assert (
        response.results
    ), "Fallback should use full catalog when category filter is empty."
    assert response.results[0].item_id == "only-one"


def test_destination_constraint_filters_results_by_city() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "lisbon-top",
                "name": "Lisbon Pick",
                "city": "Lisbon",
                "stars": 4.8,
                "review_count": 500,
                "popularity": 20.0,
                "cat_Bars": True,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": True,
                "is_open": 1,
            },
            {
                "business_id": "madrid-top",
                "name": "Madrid Pick",
                "city": "Madrid",
                "stars": 5.0,
                "review_count": 900,
                "popularity": 25.0,
                "cat_Bars": True,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": True,
                "is_open": 1,
            },
        ]
    )
    query = RecommendationQuery.model_validate(
        {
            "session_id": "test-session",
            "query": "recommend bars",
            "constraints": {"destination": "Lisbon"},
            "max_results": 5,
        }
    )

    response = recommendor_v1.recommendation_tool(query, catalog=catalog)

    assert response.results
    assert all(item.features["city"] == "Lisbon" for item in response.results)
    assert response.results[0].item_id == "lisbon-top"


def test_destination_constraint_returns_empty_when_city_not_found() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "bar-1",
                "name": "City One Bar",
                "city": "Barcelona",
                "stars": 4.6,
                "review_count": 300,
                "popularity": 18.0,
                "cat_Bars": True,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": True,
                "is_open": 1,
            }
        ]
    )
    query = RecommendationQuery.model_validate(
        {
            "session_id": "test-session",
            "query": "recommend bars",
            "constraints": {"destination": "Lisbon"},
            "max_results": 5,
        }
    )

    response = recommendor_v1.recommendation_tool(query, catalog=catalog)

    assert response.results == []


def test_item_type_filter_returns_only_requested_type() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "hotel-1",
                "item_type": "hotel",
                "name": "Hotel One",
                "city": "Santa Barbara",
                "stars": 4.5,
                "review_count": 200,
                "popularity": 20.0,
                "cat_Bars": False,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            {
                "business_id": "dest-1",
                "item_type": "destination",
                "name": "Destination One",
                "city": "Santa Barbara",
                "stars": 5.0,
                "review_count": 300,
                "popularity": 25.0,
                "cat_Bars": False,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
        ]
    )
    query = RecommendationQuery.model_validate(
        {
            "session_id": "test-session",
            "query": "recommend hotels",
            "filters": {"item_type": "hotel"},
            "max_results": 5,
        }
    )

    response = recommendor_v1.recommendation_tool(query, catalog=catalog)

    assert response.results
    assert all(item.item_type == "hotel" for item in response.results)
    assert response.results[0].item_id == "hotel-1"


def test_item_type_filter_returns_empty_when_no_requested_type() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "dest-1",
                "item_type": "destination",
                "name": "Destination One",
                "city": "Santa Barbara",
                "stars": 4.9,
                "review_count": 400,
                "popularity": 30.0,
                "cat_Bars": False,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": False,
                "is_open": 1,
            }
        ]
    )
    query = RecommendationQuery.model_validate(
        {
            "session_id": "test-session",
            "query": "recommend hotels",
            "filters": {"item_type": "hotel"},
            "max_results": 5,
        }
    )

    response = recommendor_v1.recommendation_tool(query, catalog=catalog)

    assert response.results == []


def test_keyword_matching_avoids_bar_substring_in_barbara() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "hotel-1",
                "item_type": "hotel",
                "name": "Hotel One",
                "city": "Santa Barbara",
                "stars": 4.2,
                "review_count": 150,
                "popularity": 12.0,
                "cat_Bars": False,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            {
                "business_id": "bar-1",
                "item_type": "destination",
                "name": "Bar One",
                "city": "Santa Barbara",
                "stars": 5.0,
                "review_count": 900,
                "popularity": 40.0,
                "cat_Bars": True,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": True,
                "is_open": 1,
            },
        ]
    )
    query = RecommendationQuery.model_validate(
        {
            "session_id": "test-session",
            "query": "Recommend me hotels in Santa Barbara",
            "max_results": 5,
        }
    )

    response = recommendor_v1.recommendation_tool(query, catalog=catalog)

    assert response.results
    assert response.results[0].features["category"] == "fallback_top_rated"


def test_hotel_filter_prefers_lodging_tags_over_generic_travel_tags() -> None:
    catalog = pd.DataFrame(
        [
            {
                "business_id": "hotel-generic",
                "item_type": "hotel",
                "name": "Generic Travel Listing",
                "city": "Santa Barbara",
                "stars": 5.0,
                "review_count": 1000,
                "popularity": 50.0,
                "tags": ["Hotels & Travel", "Wine Tours"],
                "cat_Bars": False,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
            {
                "business_id": "hotel-real",
                "item_type": "hotel",
                "name": "Real Hotel",
                "city": "Santa Barbara",
                "stars": 4.2,
                "review_count": 120,
                "popularity": 10.0,
                "tags": ["Hotels", "Resorts"],
                "cat_Bars": False,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Nightlife": False,
                "is_open": 1,
            },
        ]
    )
    query = RecommendationQuery.model_validate(
        {
            "session_id": "test-session",
            "query": "recommend hotels in santa barbara",
            "filters": {"item_type": "hotel"},
            "max_results": 5,
        }
    )

    response = recommendor_v1.recommendation_tool(query, catalog=catalog)

    assert response.results
    assert response.results[0].item_id == "hotel-real"
    assert all(item.item_id != "hotel-generic" for item in response.results)


def test_raw_snapshot_without_clean_columns_still_returns_results() -> None:
    raw_like_catalog = pd.DataFrame(
        [
            {
                "business_id": "rest-1",
                "name": "Raw Restaurant",
                "city": "Santa Barbara",
                "stars": 4.2,
                "review_count": 120,
                "categories": "Restaurants, Food",
                "is_open": 1,
            },
            {
                "business_id": "shop-1",
                "name": "Raw Shop",
                "city": "Santa Barbara",
                "stars": 5.0,
                "review_count": 1000,
                "categories": "Shopping, Fashion",
                "is_open": 1,
            },
        ]
    )

    response = recommendor_v1.recommendation_tool(
        _query("recommend a restaurant"), catalog=raw_like_catalog
    )

    assert response.results, "Expected recommendations from raw snapshot inputs"
    assert response.results[0].item_id == "rest-1"
    assert response.results[0].features["category"] == "cat_Restaurants"


def test_recommendation_tool_uses_database_loader_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_from_db = pd.DataFrame(
        [
            {
                "business_id": "hotel-1",
                "item_type": "hotel",
                "name": "Hotel One",
                "city": "Santa Barbara",
                "stars": 4.3,
                "review_count": 210,
                "popularity": 23.0,
                "categories": "Hotels, Travel",
                "tags": ["Hotels", "Travel"],
                "is_open": 1,
                "cat_Shopping": False,
                "cat_Restaurants": False,
                "cat_Bars": False,
                "cat_Nightlife": False,
            }
        ]
    )
    calls = {"count": 0}

    def fake_loader() -> pd.DataFrame:
        calls["count"] += 1
        return catalog_from_db

    recommendor_v1._load_catalog.cache_clear()
    monkeypatch.setattr(recommendor_v1, "_load_catalog_from_database", fake_loader)

    response = recommendor_v1.recommendation_tool(_query("recommend me a stay"))

    assert calls["count"] == 1
    assert response.results
    assert response.results[0].item_id == "hotel-1"
    assert response.results[0].item_type == "hotel"


def test_recommendation_tool_refreshes_cached_empty_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_catalog = pd.DataFrame(columns=REQUIRED_COLUMNS)
    filled_catalog = pd.DataFrame(
        [
            {
                "business_id": "rest-2",
                "item_type": "destination",
                "name": "Recovered Restaurant",
                "city": "Testville",
                "stars": 4.6,
                "review_count": 300,
                "popularity": 20.0,
                "categories": "Restaurants, Food",
                "tags": ["Restaurants", "Food"],
                "cat_Shopping": False,
                "cat_Restaurants": True,
                "cat_Bars": False,
                "cat_Nightlife": False,
                "is_open": 1,
            }
        ]
    )

    class _Loader:
        def __init__(self) -> None:
            self.calls = 0
            self.clears = 0

        def __call__(self) -> pd.DataFrame:
            self.calls += 1
            if self.calls == 1:
                return empty_catalog
            return filled_catalog

        def cache_clear(self) -> None:
            self.clears += 1

    loader = _Loader()
    monkeypatch.setattr(recommendor_v1, "_load_catalog", loader)

    response = recommendor_v1.recommendation_tool(_query("recommend restaurant"))

    assert loader.clears == 1
    assert loader.calls == 2
    assert response.results
    assert response.results[0].item_id == "rest-2"
