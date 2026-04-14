"""Tests for recommendation runtime catalog loading and tool wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from app.schemas.tools.recommendations import RecommendationQuery
from app.services.recommendation_runtime import (
    clear_recommendation_catalog_store,
    get_recommendation_catalog_store,
    get_runtime_recommendation_tool,
    preload_recommendation_catalog,
)


def _csv_style_catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": "Rome Central Hotel",
                "city": "Rome",
                "country": "IT",
                "country_name": "Italy",
                "continent": "Europe",
                "latitude": 41.9028,
                "longitude": 12.4964,
                "categories_clean": "hotel,city center",
                "description_clean": "Central stay in Rome.",
                "stars_norm": 1.1,
                "review_count_norm": 0.9,
                "popularity_norm": 1.4,
                "source_tbo_hotels": 1,
                "source_tripadvisor": 0,
                "source_openstreetmap": 0,
                "entity_type_hotel": 1,
                "entity_type_restaurant": 0,
            }
        ]
    )


def _settings_for_dataset(path: str):
    return SimpleNamespace(recommender_dataset_path=path)


def test_preload_recommendation_catalog_loads_configured_dataset(tmp_path) -> None:
    clear_recommendation_catalog_store()
    dataset_path = tmp_path / "traveltom_clean.csv"
    _csv_style_catalog().to_csv(dataset_path, index=False)

    catalog = preload_recommendation_catalog(
        settings=_settings_for_dataset(str(dataset_path))
    )

    assert not catalog.empty
    assert get_recommendation_catalog_store().dataset_path == dataset_path.resolve()


def test_runtime_recommendation_tool_uses_preloaded_catalog_without_reloading_csv(
    tmp_path, monkeypatch
) -> None:
    clear_recommendation_catalog_store()
    dataset_path = tmp_path / "traveltom_clean.csv"
    _csv_style_catalog().to_csv(dataset_path, index=False)
    settings = _settings_for_dataset(str(dataset_path))

    preload_recommendation_catalog(settings=settings)
    monkeypatch.setattr(
        "app.services.recommendation_runtime.pd.read_csv",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("runtime tool should use preloaded in-memory catalog")
        ),
    )
    tool = get_runtime_recommendation_tool(settings=settings)
    query = RecommendationQuery.model_validate(
        {
            "session_id": "sess-runtime",
            "query": "hotel in Rome",
            "constraints": {"destination": "Rome"},
            "filters": {"item_type": "hotel"},
            "max_results": 3,
            "ranking_version": "heuristic-v1",
        }
    )

    response = tool(query)

    assert response.results
    assert response.results[0].item_type == "hotel"
    assert response.results[0].features.get("city") == "Rome"
