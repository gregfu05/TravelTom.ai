"""Shared recommendation runtime catalog and tool wiring."""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Callable

import pandas as pd

from app.core.config import Settings
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationToolResponse,
)
from traveltom.recommendor import recommendor_v1, recommendor_v3

_CATALOG_SOURCE_LABEL = "catalog_items"
_ENTITY_TYPE_BY_ITEM_TYPE = {
    "hotel": "hotel",
    "restaurant": "restaurant",
    "activity": "attraction",
    "flight": "flight",
}


class RecommendationCatalogStore:
    """Thread-safe in-memory holder for the prepared runtime catalog."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._catalog: pd.DataFrame | None = None
        self._source_label: str | None = None

    def is_loaded(self) -> bool:
        with self._lock:
            return self._catalog is not None

    def preload(self, *, force_reload: bool = False) -> pd.DataFrame:
        with self._lock:
            if self._catalog is not None and not force_reload:
                return self._catalog

        if force_reload:
            _clear_v1_catalog_cache()

        loaded_catalog = _load_runtime_catalog_for_v3()
        with self._lock:
            self._catalog = loaded_catalog
            self._source_label = _CATALOG_SOURCE_LABEL
            return self._catalog

    def get_catalog(self) -> pd.DataFrame:
        with self._lock:
            if self._catalog is None:
                raise RuntimeError("Recommendation catalog was not preloaded")
            return self._catalog

    def clear(self) -> None:
        with self._lock:
            self._catalog = None
            self._source_label = None

    @property
    def source_label(self) -> str | None:
        with self._lock:
            return self._source_label


@lru_cache(maxsize=1)
def get_recommendation_catalog_store() -> RecommendationCatalogStore:
    return RecommendationCatalogStore()


def preload_recommendation_catalog(settings: Settings | None = None) -> pd.DataFrame:
    del settings
    store = get_recommendation_catalog_store()
    return store.preload(force_reload=True)


def get_runtime_recommendation_tool(
    *,
    settings: Settings | None = None,
) -> Callable[[RecommendationQuery], RecommendationToolResponse]:
    del settings
    store = get_recommendation_catalog_store()

    def _tool(query: RecommendationQuery) -> RecommendationToolResponse:
        if not store.is_loaded():
            store.preload()

        catalog = store.get_catalog()
        if catalog.empty:
            catalog = store.preload(force_reload=True)

        return recommendor_v3.recommendation_tool(
            query=query,
            catalog=catalog,
            catalog_prepared=True,
        )

    return _tool


def clear_recommendation_catalog_store() -> None:
    _clear_v1_catalog_cache()
    get_recommendation_catalog_store().clear()


def _clear_v1_catalog_cache() -> None:
    cache_clear = getattr(recommendor_v1._load_catalog, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def _load_runtime_catalog_for_v3() -> pd.DataFrame:
    """Load the PostgreSQL-backed runtime catalog and normalize it for v3."""

    raw_catalog = recommendor_v1._load_catalog()
    if raw_catalog.empty:
        return pd.DataFrame()

    working = raw_catalog.copy()

    if "entity_type" not in working.columns and "item_type" in working.columns:
        working["entity_type"] = (
            working["item_type"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.lower()
            .map(_ENTITY_TYPE_BY_ITEM_TYPE)
            .fillna("destination")
        )

    if "categories" not in working.columns and "tags" in working.columns:
        working["categories"] = working["tags"].apply(_tags_to_categories)
    elif "tags" in working.columns:
        empty_categories = working["categories"].isna() | (
            working["categories"].astype("string").fillna("").str.strip() == ""
        )
        working.loc[empty_categories, "categories"] = working.loc[
            empty_categories, "tags"
        ].apply(_tags_to_categories)

    if "description" not in working.columns:
        working["description"] = ""
    if "source" not in working.columns:
        working["source"] = _CATALOG_SOURCE_LABEL
    if "country" not in working.columns:
        working["country"] = ""
    if "country_name" not in working.columns:
        working["country_name"] = ""
    if "state" not in working.columns:
        working["state"] = ""
    if "continent" not in working.columns:
        working["continent"] = ""

    return recommendor_v3.prepare_catalog_for_v3(catalog=working)


def _tags_to_categories(value: object) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return ""


__all__ = [
    "RecommendationCatalogStore",
    "clear_recommendation_catalog_store",
    "get_recommendation_catalog_store",
    "get_runtime_recommendation_tool",
    "preload_recommendation_catalog",
]
