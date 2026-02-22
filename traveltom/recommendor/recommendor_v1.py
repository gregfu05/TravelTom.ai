"""Minimal deterministic recommender used by the API recommendation tool."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)

DATASET_NAME = "business_SB_cleaned.parquet"

# Keyword → category column mapping. Order matters for matching priority.
CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("nightlife", "cat_Nightlife"),
    ("bar", "cat_Bars"),
    ("bars", "cat_Bars"),
    ("restaurant", "cat_Restaurants"),
    ("food", "cat_Restaurants"),
    ("dinner", "cat_Restaurants"),
    ("shop", "cat_Shopping"),
    ("shopping", "cat_Shopping"),
    ("store", "cat_Shopping"),
]

_EMPTY_COLUMNS = [
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


def recommendation_tool(
    query: RecommendationQuery,
    catalog: pd.DataFrame | None = None,
) -> RecommendationToolResponse:
    """Return ranked recommendations for the given query.

    Args:
        query: Validated recommendation request.
        catalog: Optional preloaded catalog (used in unit tests).

    Returns:
        RecommendationToolResponse containing up to max_results results.
    """

    catalog_df = catalog if catalog is not None else _load_catalog()
    if catalog_df.empty:
        return RecommendationToolResponse(
            results=[], ranking_version=query.ranking_version
        )

    category_column = _infer_category(query.query)
    candidates = _filter_candidates(catalog_df, category_column)
    if candidates.empty:
        candidates = catalog_df
        category_column = None

    ranked = _rank_candidates(candidates)
    max_results = _normalize_max_results(query.max_results)

    results: list[RecommendationResult] = []
    for rank, row in enumerate(
        ranked.head(max_results).itertuples(index=False), start=1
    ):
        results.append(
            RecommendationResult(
                item_id=str(row.business_id),
                item_type="destination",
                score=float(row.score),
                rank=rank,
                features={
                    "name": row.name,
                    "city": row.city,
                    "stars": float(row.stars),
                    "review_count": int(row.review_count),
                    "popularity": float(row.popularity),
                    "category": category_column or "fallback_top_rated",
                },
                explanation=_build_explanation(category_column, row.name),
            )
        )

    return RecommendationToolResponse(
        results=results, ranking_version=query.ranking_version
    )


@lru_cache()
def _load_catalog() -> pd.DataFrame:
    """Load and cache the cleaned business catalog.

    Returns:
        DataFrame containing cleaned business records, or an empty catalog
        when the dataset is unavailable.
    """

    dataset_path = Path(__file__).with_name(DATASET_NAME)
    if not dataset_path.exists():
        return _empty_catalog()

    try:
        catalog = pd.read_parquet(dataset_path)
    except (FileNotFoundError, OSError):
        return _empty_catalog()
    if "is_open" in catalog.columns:
        catalog = catalog[catalog["is_open"] == 1]
    catalog = catalog.copy()
    catalog["popularity"] = catalog["popularity"].fillna(0.0)
    return catalog


def _infer_category(request_text: str) -> str | None:
    """Return the matching category column for the user request.

    Args:
        request_text: Raw user request text.

    Returns:
        Category column name or None when no keyword matches.
    """

    normalized = request_text.lower()
    for keyword, column in CATEGORY_KEYWORDS:
        if keyword in normalized:
            return column
    return None


def _filter_candidates(
    catalog: pd.DataFrame, category_column: str | None
) -> pd.DataFrame:
    """Filter catalog by category when available.

    Args:
        catalog: Full catalog DataFrame.
        category_column: Column name to filter on.

    Returns:
        Filtered DataFrame when the category exists, otherwise the original.
    """

    if category_column and category_column in catalog.columns:
        filtered = catalog[catalog[category_column]]
        if not filtered.empty:
            return filtered
    return catalog


def _rank_candidates(catalog: pd.DataFrame) -> pd.DataFrame:
    """Compute scores and return candidates sorted deterministically."""

    working = catalog.copy()
    if working.empty:
        return working

    working["score"] = (
        working["stars"]
        + 0.25 * np.log1p(working["review_count"])
        + 0.25 * working["popularity"]
    )

    ranked = working.sort_values(
        by=["score", "review_count", "popularity", "business_id"],
        ascending=[False, False, False, True],
        kind="mergesort",
    )
    return ranked


def _build_explanation(category_column: str | None, business_name: str) -> str:
    """Create a brief explanation for the recommendation.

    Args:
        category_column: Selected category column name, if any.
        business_name: Name of the chosen business.

    Returns:
        Short explanation string for the API response.
    """

    if category_column:
        category_label = category_column.replace("cat_", "").replace("_", " ").lower()
        return f"Top {category_label} option by score: {business_name}."
    return f"Top overall option by score: {business_name}."


def _empty_catalog() -> pd.DataFrame:
    """Return an empty catalog with required columns for safe fallback."""

    return pd.DataFrame(columns=_EMPTY_COLUMNS)


def _normalize_max_results(max_results: int | None) -> int:
    """Ensure max_results is a positive integer, defaulting to 5."""

    if isinstance(max_results, int) and max_results > 0:
        return max_results
    return 5


__all__ = ["recommendation_tool"]
