"""Shared recommendation runtime catalog and tool wiring."""

from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path
from typing import Callable

import pandas as pd

from app.core.config import Settings, get_settings
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationToolResponse,
)
from app.services.recommendation_query import RecommendationTool
from traveltom.recommendor.recommendor_v3 import (
    prepare_catalog_for_v3,
)
from traveltom.recommendor.recommendor_v3 import (
    recommendation_tool as recommendation_tool_v3,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RECOMMENDER_DATASET_PATH = (
    REPO_ROOT / "traveltom" / "datasets" / "traveltom_clean.csv"
)


class RecommendationCatalogStore:
    """Thread-safe in-memory holder for the prepared recommender catalog."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._catalog: pd.DataFrame | None = None
        self._dataset_path: Path | None = None

    def is_loaded(self) -> bool:
        with self._lock:
            return self._catalog is not None

    def preload_from_csv(self, dataset_path: Path) -> pd.DataFrame:
        resolved_path = dataset_path.expanduser().resolve()
        with self._lock:
            if self._catalog is not None and self._dataset_path == resolved_path:
                return self._catalog

        if not resolved_path.exists():
            raise FileNotFoundError(
                f"Recommendation dataset not found: {resolved_path}"
            )

        raw_catalog = pd.read_csv(resolved_path, low_memory=False)
        prepared_catalog = prepare_catalog_for_v3(catalog=raw_catalog)
        with self._lock:
            self._catalog = prepared_catalog
            self._dataset_path = resolved_path
            return self._catalog

    def get_catalog(self) -> pd.DataFrame:
        with self._lock:
            if self._catalog is None:
                raise RuntimeError("Recommendation catalog was not preloaded")
            return self._catalog

    def clear(self) -> None:
        with self._lock:
            self._catalog = None
            self._dataset_path = None

    @property
    def dataset_path(self) -> Path | None:
        with self._lock:
            return self._dataset_path


def _resolve_dataset_path(settings: Settings) -> Path:
    configured_path = settings.recommender_dataset_path.strip()
    if not configured_path:
        return DEFAULT_RECOMMENDER_DATASET_PATH
    configured = Path(configured_path).expanduser()
    if configured.is_absolute():
        return configured
    return (REPO_ROOT / configured).resolve()


@lru_cache(maxsize=1)
def get_recommendation_catalog_store() -> RecommendationCatalogStore:
    return RecommendationCatalogStore()


def preload_recommendation_catalog(settings: Settings | None = None) -> pd.DataFrame:
    active_settings = settings or get_settings()
    store = get_recommendation_catalog_store()
    return store.preload_from_csv(_resolve_dataset_path(active_settings))


def get_runtime_recommendation_tool(
    *,
    settings: Settings | None = None,
) -> Callable[[RecommendationQuery], RecommendationToolResponse]:
    active_settings = settings or get_settings()
    store = get_recommendation_catalog_store()
    dataset_path = _resolve_dataset_path(active_settings)

    def _tool(query: RecommendationQuery) -> RecommendationToolResponse:
        store.preload_from_csv(dataset_path)
        return recommendation_tool_v3(
            query=query,
            catalog=store.get_catalog(),
            catalog_prepared=True,
        )

    return _tool


def clear_recommendation_catalog_store() -> None:
    get_recommendation_catalog_store().clear()


__all__ = [
    "DEFAULT_RECOMMENDER_DATASET_PATH",
    "RecommendationCatalogStore",
    "clear_recommendation_catalog_store",
    "get_recommendation_catalog_store",
    "get_runtime_recommendation_tool",
    "preload_recommendation_catalog",
]
