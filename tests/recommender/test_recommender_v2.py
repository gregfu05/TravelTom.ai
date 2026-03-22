"""Tests for recommender_v2 behavior."""

from __future__ import annotations

import pandas as pd

from app.schemas.tools.recommendations import RecommendationQuery
from traveltom.recommendor import recommendor_v2


def _query(text: str, max_results: int | None = None) -> RecommendationQuery:
    return RecommendationQuery(
        session_id="sess",
        query=text,
        max_results=max_results if max_results is not None else 5,
    )


def _catalog() -> pd.DataFrame:
    """Synthetic catalog covering categories and attributes."""

    base = {
        "attributes": None,
        "categories": None,
        "categories_list": [],
        "is_open": 1,
    }
    rows = [
        {
            **base,
            "business_id": "bar1",
            "name": "Late Bar",
            "latitude": 1.0,
            "longitude": 2.0,
            "stars": 4.5,
            "review_count": 200,
            "popularity": 1.2,
            "cat_Bars": True,
            "cat_Nightlife": True,
            "late_night": True,
            "attr_parking_street": True,
            "attr_GoodForKids": False,
        },
        {
            **base,
            "business_id": "bar2",
            "name": "Early Bar",
            "latitude": 1.1,
            "longitude": 2.1,
            "stars": 4.7,
            "review_count": 50,
            "popularity": 0.2,
            "cat_Bars": True,
            "cat_Nightlife": False,
            "late_night": False,
            "attr_parking_street": False,
            "attr_GoodForKids": True,
        },
        {
            **base,
            "business_id": "burger1",
            "name": "Burger Place",
            "latitude": 1.2,
            "longitude": 2.2,
            "stars": 4.8,
            "review_count": 500,
            "popularity": 0.9,
            "cat_Burgers": True,
            "cat_Restaurants": True,
            "late_night": True,
            "attr_parking_garage": True,
            "attr_wifi_free": True,
        },
        {
            **base,
            "business_id": "pizza1",
            "name": "Pizza House",
            "latitude": 1.3,
            "longitude": 2.3,
            "stars": 4.2,
            "review_count": 300,
            "popularity": 0.7,
            "cat_Pizza": True,
            "cat_Food": True,
            "late_night": False,
        },
        {
            **base,
            "business_id": "coffee1",
            "name": "Coffee Spot",
            "latitude": 1.4,
            "longitude": 2.4,
            "stars": 4.9,
            "review_count": 120,
            "popularity": 0.4,
            "cat_Coffee_and_Tea": True,
            "late_night": False,
            "attr_wifi_free": True,
        },
        {
            **base,
            "business_id": "bar3",
            "name": "Third Bar",
            "latitude": 1.5,
            "longitude": 2.5,
            "stars": 4.3,
            "review_count": 80,
            "popularity": 0.1,
            "cat_Bars": True,
            "late_night": True,
        },
    ]
    return pd.DataFrame(rows).fillna(0)


def test_default_top_five() -> None:
    response = recommendor_v2.recommendation_tool(_query("bars"), catalog=_catalog())
    assert len(response.results) == 5


def test_custom_top_n_within_bounds() -> None:
    response = recommendor_v2.recommendation_tool(
        _query("top 3 bars"), catalog=_catalog()
    )
    assert len(response.results) == 3
    assert response.results[0].rank == 1
    assert response.results[-1].rank == 3


def test_request_over_ten_caps_at_ten() -> None:
    response = recommendor_v2.recommendation_tool(
        _query("top 15 bars", max_results=15), catalog=_catalog()
    )
    assert len(response.results) <= 10
    assert any(res.features.get("limit_notice") for res in response.results)
    assert response.ranking_version == "recommender-v2"


def test_category_filter_burgers() -> None:
    response = recommendor_v2.recommendation_tool(
        _query("burger spots"), catalog=_catalog()
    )
    assert response.results
    assert response.results[0].features["name"] == "Burger Place"


def test_attribute_filters_late_night_and_parking() -> None:
    response = recommendor_v2.recommendation_tool(
        _query("late night bar with parking"), catalog=_catalog()
    )
    assert response.results
    assert response.results[0].features["name"] == "Late Bar"


def test_wifi_filter() -> None:
    response = recommendor_v2.recommendation_tool(
        _query("coffee with wifi"), catalog=_catalog()
    )
    assert response.results
    assert response.results[0].features["name"] == "Coffee Spot"


def test_result_includes_map_url() -> None:
    response = recommendor_v2.recommendation_tool(_query("bars"), catalog=_catalog())
    assert response.results
    assert (
        response.results[0]
        .features["map_url"]
        .startswith("https://www.google.com/maps?q=")
    )


def test_phrase_parsing_full_bar_and_wifi() -> None:
    response = recommendor_v2.recommendation_tool(
        _query("bar with full bar and free wifi"), catalog=_catalog()
    )
    assert response.results


def test_categories_list_matching() -> None:
    df = _catalog()
    df.loc[0, "categories_list"] = ["Beauty & Spas"]
    response = recommendor_v2.recommendation_tool(_query("beauty and spa"), catalog=df)
    assert response.results


def test_no_matches_returns_empty() -> None:
    response = recommendor_v2.recommendation_tool(
        _query("vegan cat cafes with bowling"), catalog=_catalog()
    )
    assert response.results == []


def test_city_filter_applies_first() -> None:
    df = _catalog()
    df.loc[0, "city"] = "seattle"
    df.loc[1, "city"] = "new york"
    response = recommendor_v2.recommendation_tool(_query("bars in seattle"), catalog=df)
    assert response.results
    assert all(
        res.features.get("city", "").lower().find("seattle") != -1
        for res in response.results
    )


def test_city_not_found_returns_message() -> None:
    df = _catalog()
    df["city"] = "seattle"
    response = recommendor_v2.recommendation_tool(_query("bars in berlin"), catalog=df)
    assert len(response.results) == 1
    assert "don't have places for berlin" in response.results[0].features["name"]
