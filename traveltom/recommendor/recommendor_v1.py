"""Minimal deterministic recommender used by the API recommendation tool."""

from __future__ import annotations

import asyncio
import json
import re
from functools import lru_cache
from typing import Any

import asyncpg
import numpy as np
import pandas as pd
from app.core.config import get_settings
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)

# Keyword -> category column mapping. Order matters for matching priority.
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

_CATEGORY_FALLBACK_PATTERNS: dict[str, str] = {
    "cat_Shopping": r"\bshopping\b|\bshop\b|\bstore\b|\bfashion\b|\bboutique\b",
    "cat_Restaurants": (
        r"\brestaurant\b|\bfood\b|\bcafe\b|\bdiner\b|\bpizza\b|\bbreakfast\b"
    ),
    "cat_Bars": r"\bbar\b|\bpub\b|\bbrewery\b|\bcocktail\b|\bwine\b",
    "cat_Nightlife": r"\bnightlife\b|\bnight\s+club\b|\bclub\b|\bdance\b|\bkaraoke\b",
}

_VALID_ITEM_TYPES = {"hotel", "restaurant", "activity"}
_HOTEL_LODGING_TAGS = {
    "hotel",
    "hotels",
    "hostel",
    "hostels",
    "resort",
    "resorts",
    "lodging",
    "bed and breakfast",
    "vacation rental",
    "vacation rentals",
    "guest house",
    "guest houses",
    "motel",
    "motels",
    "inn",
    "inns",
}

_EMPTY_COLUMNS = [
    "business_id",
    "item_type",
    "name",
    "city",
    "stars",
    "review_count",
    "popularity",
    "categories",
    "tags",
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
    if catalog is None and catalog_df.empty:
        _load_catalog.cache_clear()
        catalog_df = _load_catalog()
    catalog_df = _prepare_catalog(catalog_df)
    if catalog_df.empty:
        return RecommendationToolResponse(
            results=[], ranking_version=query.ranking_version
        )

    location_filtered = _apply_destination_filter(
        catalog_df, query.constraints.destination
    )
    if query.constraints.destination and location_filtered.empty:
        return RecommendationToolResponse(
            results=[],
            ranking_version=query.ranking_version,
        )

    requested_item_type = _extract_requested_item_type(query.filters)
    type_filtered = _apply_item_type_filter(location_filtered, requested_item_type)
    if requested_item_type and type_filtered.empty:
        return RecommendationToolResponse(
            results=[],
            ranking_version=query.ranking_version,
        )

    category_column = _infer_category(query.query)
    candidates = _filter_candidates(type_filtered, category_column)
    if candidates.empty:
        candidates = type_filtered
        category_column = None

    ranked = _rank_candidates(candidates)
    max_results = _normalize_max_results(query.max_results)

    results: list[RecommendationResult] = []
    for rank, row in enumerate(
        ranked.head(max_results).itertuples(index=False), start=1
    ):
        item_type = row.item_type if row.item_type in _VALID_ITEM_TYPES else "activity"
        results.append(
            RecommendationResult(
                item_id=str(row.business_id),
                item_type=item_type,
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
    """Load and cache the catalog snapshot from PostgreSQL."""

    return _load_catalog_from_database()


def _load_catalog_from_database() -> pd.DataFrame:
    rows = asyncio.run(_fetch_catalog_rows())

    if not rows:
        return _empty_catalog()

    records: list[dict[str, Any]] = []
    for row in rows:
        metadata = _coerce_metadata_json(row.get("metadata_json"))
        tags = row["tags"] if isinstance(row["tags"], list) else []

        business_id = str(metadata.get("business_id") or row["id"])
        parsed_stars = _to_float(
            row["rating"],
            default=_to_float(metadata.get("stars"), 0.0),
        )
        stars = parsed_stars if parsed_stars is not None else 0.0
        review_count = _to_int(metadata.get("review_count"), default=0)
        popularity = _to_float(metadata.get("popularity"))
        if popularity is None:
            popularity = stars * float(np.log1p(review_count))

        raw_item_type = str(row["item_type"] or "activity")
        item_type = raw_item_type if raw_item_type in _VALID_ITEM_TYPES else "activity"

        records.append(
            {
                "business_id": business_id,
                "item_type": item_type,
                "name": str(row["name"] or business_id),
                "city": str(row["location_city"] or ""),
                "stars": stars,
                "review_count": review_count,
                "popularity": popularity,
                "categories": str(
                    metadata.get("categories") or row["description"] or ""
                ),
                "tags": tags,
                "is_open": _to_int(metadata.get("is_open"), default=1),
            }
        )

    return pd.DataFrame.from_records(records)


async def _fetch_catalog_rows() -> list[dict[str, Any]]:
    connection = await asyncpg.connect(_database_url_for_asyncpg())
    try:
        rows = await connection.fetch(
            """
            SELECT
                id::text AS id,
                item_type,
                name,
                description,
                location_city,
                rating,
                tags,
                metadata_json
            FROM catalog_items
            """
        )
        return [dict(row) for row in rows]
    finally:
        await connection.close()


@lru_cache()
def _database_url_for_asyncpg() -> str:
    url = get_settings().database_url
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "", 1)
    return url


def _prepare_catalog(catalog: pd.DataFrame) -> pd.DataFrame:
    """Normalize catalog columns so ranking can operate deterministically."""

    if catalog.empty:
        return _empty_catalog()

    working = catalog.copy()

    if "is_open" in working.columns:
        working = working[working["is_open"] == 1]
    if working.empty:
        return _empty_catalog()

    _ensure_required_columns(working)
    _ensure_category_columns(working)
    _ensure_popularity(working)

    return working


def _ensure_required_columns(catalog: pd.DataFrame) -> None:
    if "business_id" not in catalog.columns:
        catalog["business_id"] = catalog.index.map(str)
    if "item_type" not in catalog.columns:
        catalog["item_type"] = "activity"
    if "name" not in catalog.columns:
        catalog["name"] = catalog["business_id"]
    if "city" not in catalog.columns:
        catalog["city"] = ""
    if "stars" not in catalog.columns:
        catalog["stars"] = 0.0
    if "review_count" not in catalog.columns:
        catalog["review_count"] = 0
    if "categories" not in catalog.columns:
        catalog["categories"] = ""
    if "tags" not in catalog.columns:
        catalog["tags"] = [[] for _ in range(len(catalog))]
    if "is_open" not in catalog.columns:
        catalog["is_open"] = 1

    catalog["item_type"] = catalog["item_type"].apply(
        lambda value: value if value in _VALID_ITEM_TYPES else "activity"
    )
    catalog["stars"] = pd.to_numeric(catalog["stars"], errors="coerce").fillna(0.0)
    catalog["review_count"] = (
        pd.to_numeric(catalog["review_count"], errors="coerce").fillna(0).astype(int)
    )


def _ensure_category_columns(catalog: pd.DataFrame) -> None:
    category_text = catalog["categories"].fillna("").astype(str).str.lower()
    tag_text = catalog["tags"].apply(_tag_text_from_value)
    merged_text = (category_text + " " + tag_text).str.strip()

    for column, pattern in _CATEGORY_FALLBACK_PATTERNS.items():
        if column not in catalog.columns:
            catalog[column] = merged_text.str.contains(pattern, regex=True)
        else:
            catalog[column] = catalog[column].fillna(False).astype(bool)


def _ensure_popularity(catalog: pd.DataFrame) -> None:
    if "popularity" not in catalog.columns:
        catalog["popularity"] = catalog["stars"] * np.log1p(catalog["review_count"])
    else:
        catalog["popularity"] = pd.to_numeric(
            catalog["popularity"], errors="coerce"
        ).fillna(0.0)


def _tag_text_from_value(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item).lower() for item in value)
    return ""


def _to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_metadata_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _infer_category(request_text: str) -> str | None:
    """Return the matching category column for the user request.

    Args:
        request_text: Raw user request text.

    Returns:
        Category column name or None when no keyword matches.
    """

    normalized = request_text.casefold()
    for keyword, column in CATEGORY_KEYWORDS:
        if _contains_keyword(normalized, keyword):
            return column
    return None


def _contains_keyword(text: str, keyword: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.casefold())}(?![a-z0-9])"
    return re.search(pattern, text) is not None


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


def _apply_destination_filter(
    catalog: pd.DataFrame, destination: str | None
) -> pd.DataFrame:
    """Apply a hard location constraint when destination is provided."""

    if not destination:
        return catalog
    if "city" not in catalog.columns:
        return catalog

    normalized_destination = _normalize_filter_text(destination)
    if not normalized_destination:
        return catalog

    normalized_city = (
        catalog["city"].fillna("").astype(str).apply(_normalize_filter_text)
    )
    matches = normalized_city == normalized_destination
    if not bool(matches.any()):
        escaped_destination = re.escape(normalized_destination)
        matches = normalized_city.str.contains(escaped_destination, regex=True)

    filtered = catalog[matches]
    if filtered.empty:
        return catalog.iloc[0:0]
    return filtered


def _extract_requested_item_type(filters: dict[str, Any]) -> str | None:
    value = filters.get("item_type")
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    if normalized in {"hotel", "hotels"}:
        return "hotel"
    if normalized in {"restaurant", "restaurants"}:
        return "restaurant"
    if normalized in {"activity", "activities"}:
        return "activity"
    return None


def _apply_item_type_filter(
    catalog: pd.DataFrame,
    item_type: str | None,
) -> pd.DataFrame:
    if not item_type:
        return catalog
    if "item_type" not in catalog.columns:
        return catalog
    filtered = catalog[catalog["item_type"] == item_type]
    if filtered.empty:
        return catalog.iloc[0:0]
    if item_type == "hotel":
        filtered = _apply_hotel_quality_filter(filtered)
    return filtered


def _apply_hotel_quality_filter(catalog: pd.DataFrame) -> pd.DataFrame:
    if "tags" not in catalog.columns:
        return catalog
    lodging_mask = catalog["tags"].apply(_has_lodging_tag)
    if bool(lodging_mask.any()):
        narrowed = catalog[lodging_mask]
        if not narrowed.empty:
            return narrowed
    return catalog


def _has_lodging_tag(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    normalized_tags = {_normalize_tag_text(str(tag)) for tag in value}
    return bool(normalized_tags & _HOTEL_LODGING_TAGS)


def _normalize_tag_text(value: str) -> str:
    cleaned = value.casefold().strip()
    cleaned = cleaned.replace("&", " and ")
    return re.sub(r"\s+", " ", cleaned)


def _normalize_filter_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", value.casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


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
