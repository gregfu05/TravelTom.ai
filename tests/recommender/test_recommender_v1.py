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
    return RecommendationQuery(session_id="test-session", query=text, max_results=1)


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
    assert response.results == []


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
