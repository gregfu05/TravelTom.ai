"""Tests for recommendation runtime catalog loading and tool wiring."""

from __future__ import annotations

import pandas as pd
from app.schemas.tools.recommendations import RecommendationQuery
from app.services.recommendation_runtime import (
    clear_recommendation_catalog_store,
    get_recommendation_catalog_store,
    get_runtime_recommendation_tool,
    preload_recommendation_catalog,
)


def _catalog_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "business_id": "hotel-rome-1",
                "item_type": "hotel",
                "name": "Rome Central Hotel",
                "city": "Rome",
                "stars": 4.4,
                "review_count": 220,
                "popularity": 14.8,
                "categories": "Hotels, City Center",
                "tags": ["Hotels", "City Center"],
                "is_open": 1,
            }
        ]
    )


def _query() -> RecommendationQuery:
    return RecommendationQuery.model_validate(
        {
            "session_id": "sess-runtime",
            "query": "hotel in Rome",
            "constraints": {"destination": "Rome"},
            "filters": {"item_type": "hotel"},
            "max_results": 3,
            "ranking_version": "heuristic-v1",
        }
    )


def test_preload_recommendation_catalog_loads_runtime_catalog(monkeypatch) -> None:
    clear_recommendation_catalog_store()
    monkeypatch.setattr(
        "app.services.recommendation_runtime.recommendor_v1._load_catalog",
        lambda: _catalog_rows(),
    )

    catalog = preload_recommendation_catalog()

    assert not catalog.empty
    assert get_recommendation_catalog_store().source_label == "catalog_items"
    assert "entity_type_norm" in catalog.columns
    assert str(catalog.iloc[0]["entity_type"]) == "hotel"


def test_runtime_recommendation_tool_uses_preloaded_catalog_without_reloading(
    monkeypatch,
) -> None:
    clear_recommendation_catalog_store()
    load_calls = {"count": 0}

    def fake_load_catalog() -> pd.DataFrame:
        load_calls["count"] += 1
        return _catalog_rows()

    monkeypatch.setattr(
        "app.services.recommendation_runtime.recommendor_v1._load_catalog",
        fake_load_catalog,
    )
    preload_recommendation_catalog()

    tool = get_runtime_recommendation_tool()
    response = tool(_query())

    assert load_calls["count"] == 1
    assert response.results
    assert response.results[0].item_type == "hotel"
    assert response.ranking_version.startswith("recommender-v3:")
    assert response.results[0].features.get("city") == "Rome"
    assert response.results[0].features.get("entity_type") == "hotel"


def test_runtime_recommendation_tool_reloads_when_cached_catalog_is_empty(
    monkeypatch,
) -> None:
    clear_recommendation_catalog_store()
    load_calls = {"count": 0}

    def fake_load_catalog() -> pd.DataFrame:
        load_calls["count"] += 1
        if load_calls["count"] == 1:
            return pd.DataFrame()
        return _catalog_rows()

    monkeypatch.setattr(
        "app.services.recommendation_runtime.recommendor_v1._load_catalog",
        fake_load_catalog,
    )

    tool = get_runtime_recommendation_tool()
    response = tool(_query())

    assert load_calls["count"] == 2
    assert response.results
    assert response.ranking_version.startswith("recommender-v3:")
