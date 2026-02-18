"""Minimal deterministic recommender used by the API recommendation tool."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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


def recommendation_tool(
    query: RecommendationQuery,
    catalog: pd.DataFrame | None = None,
) -> RecommendationToolResponse:
    """Return a single top recommendation for the given query.

    Args:
        query: Validated recommendation request.
        catalog: Optional preloaded catalog (used in unit tests).

    Returns:
        RecommendationToolResponse containing at most one result.
    """

    catalog_df = catalog if catalog is not None else _load_catalog()
    category_column = _infer_category(query.query)
    candidates = _filter_candidates(catalog_df, category_column)
    top_row = _select_top_row(candidates)

    if top_row is None:
        return RecommendationToolResponse(results=[], ranking_version=query.ranking_version)

    result = RecommendationResult(
        item_id=str(top_row["business_id"]),
        item_type="destination",
        score=float(top_row["stars"]),
        rank=1,
        features={
            "name": top_row["name"],
            "city": top_row["city"],
            "stars": float(top_row["stars"]),
            "review_count": int(top_row["review_count"]),
            "popularity": float(top_row["popularity"]),
            "category": category_column or "fallback_top_rated",
        },
        explanation=_build_explanation(category_column, top_row["name"]),
    )
    return RecommendationToolResponse(
        results=[result],
        ranking_version=query.ranking_version,
    )


@lru_cache()
def _load_catalog() -> pd.DataFrame:
    """Load and cache the cleaned business catalog.

    Returns:
        DataFrame containing cleaned business records.

    Raises:
        FileNotFoundError: If the parquet dataset is missing.
    """

    dataset_path = Path(__file__).with_name(DATASET_NAME)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")

    catalog = pd.read_parquet(dataset_path)
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


def _filter_candidates(catalog: pd.DataFrame, category_column: str | None) -> pd.DataFrame:
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


def _select_top_row(catalog: pd.DataFrame) -> pd.Series | None:
    """Select the top row using deterministic tie-breaking.

    Args:
        catalog: Candidate DataFrame.

    Returns:
        Top-ranked row or None when no rows are present.
    """

    if catalog.empty:
        return None

    ranked = catalog.sort_values(
        by=["stars", "review_count", "popularity", "business_id"],
        ascending=[False, False, False, True],
        kind="mergesort",
    )
    return ranked.iloc[0]


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
        return f"Top {category_label} option by rating: {business_name}."
    return f"Top overall option by rating: {business_name}."


__all__ = ["recommendation_tool"]
