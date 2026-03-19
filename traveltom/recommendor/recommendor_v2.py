"""Improved recommender (v2) built for the cleaned Yelp dataset."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)

DATASET_NAME = "cleaned_Yelp_DS.parquet"
RANKING_VERSION = "recommender-v2"

# Categories that we can map from user intent to dataset columns.
CATEGORY_KEYWORDS: dict[str, str] = {
    "bar": "cat_Bars",
    "bars": "cat_Bars",
    "nightlife": "cat_Nightlife",
    "restaurant": "cat_Restaurants",
    "restaurants": "cat_Restaurants",
    "food": "cat_Food",
    "shopping": "cat_Shopping",
    "shop": "cat_Shopping",
    "beauty": "cat_Beauty_and_Spas",
    "spa": "cat_Beauty_and_Spas",
    "hair": "cat_Beauty_and_Spas",
    "coffee": "cat_Coffee_and_Tea",
    "tea": "cat_Coffee_and_Tea",
    "breakfast": "cat_Breakfast_and_Brunch",
    "brunch": "cat_Breakfast_and_Brunch",
    "pizza": "cat_Pizza",
    "sandwich": "cat_Sandwiches",
    "sandwiches": "cat_Sandwiches",
    "burger": "cat_Burgers",
    "burgers": "cat_Burgers",
    "fast food": "cat_Fast_Food",
    "hotel": "cat_Hotels_and_Travel",
    "travel": "cat_Hotels_and_Travel",
    "active": "cat_Active_Life",
    "gym": "cat_Active_Life",
    "automotive": "cat_Automotive",
    "car": "cat_Automotive",
}

# Attribute keyword mapping to boolean columns.
ATTRIBUTE_KEYWORDS: dict[str, str] = {
    "outdoor": "attr_OutdoorSeating",
    "outdoor seating": "attr_OutdoorSeating",
    "kid": "attr_GoodForKids",
    "kids": "attr_GoodForKids",
    "family": "attr_GoodForKids",
    "reservation": "attr_RestaurantsReservations",
    "reservations": "attr_RestaurantsReservations",
    "wifi": "attr_wifi_free",
    "free wifi": "attr_wifi_free",
    "paid wifi": "attr_wifi_paid",
    "beer": "attr_alcohol_beer_and_wine",
    "wine": "attr_alcohol_beer_and_wine",
    "full bar": "attr_alcohol_full_bar",
    "alcohol": "attr_alcohol_full_bar",
}

PARKING_COLUMNS = [
    "attr_parking_garage",
    "attr_parking_street",
    "attr_parking_lot",
    "attr_parking_valet",
    "attr_parking_validated",
]


@dataclass
class ParsedIntent:
    categories: set[str]
    require_late_night: bool
    require_parking: bool
    require_burgers: bool
    attributes: set[str]
    price_tier: str | None
    requested_results: int | None
    city: str | None


def recommendation_tool(
    query: RecommendationQuery,
    catalog: pd.DataFrame | None = None,
) -> RecommendationToolResponse:
    """Return ranked recommendations using the Yelp dataset."""

    catalog_df = catalog if catalog is not None else _load_catalog()
    if catalog_df.empty:
        return RecommendationToolResponse(results=[], ranking_version=RANKING_VERSION)

    intent = _parse_intent(query.query)
    requested = intent.requested_results
    if requested is None and query.max_results is not None and 1 <= query.max_results <= 10:
        requested = query.max_results
    max_results, limit_notice = _normalize_requested_results(requested)

    candidates = _apply_filters(catalog_df, intent)
    if candidates.empty:
        return RecommendationToolResponse(results=[], ranking_version=RANKING_VERSION)

    ranked = _rank_candidates(candidates)
    results: list[RecommendationResult] = []
    for rank, row in enumerate(ranked.head(max_results).itertuples(index=False), start=1):
        map_url = _build_map_url(row.latitude, row.longitude)
        if map_url is None:
            continue
        features = {
            "name": row.name,
            "map_url": map_url,
            "city": getattr(row, "city", None),
        }
        if limit_notice:
            features["limit_notice"] = limit_notice
        results.append(
            RecommendationResult(
                item_id=str(row.business_id),
                item_type="destination",
                score=float(row.score),
                rank=rank,
                features=features,
                explanation=_build_explanation(row.name, max_results, limit_notice, intent),
            )
        )

    return RecommendationToolResponse(results=results, ranking_version=RANKING_VERSION)


@lru_cache()
def _load_catalog() -> pd.DataFrame:
    dataset_path = Path(__file__).parent / "datasets" / DATASET_NAME
    if not dataset_path.exists():
        # Fallback to repository root location
        dataset_path = Path(__file__).parent.parent / "datasets" / DATASET_NAME
    if not dataset_path.exists():
        return pd.DataFrame()

    df = pd.read_parquet(dataset_path)
    if "is_open" in df.columns:
        df = df[df["is_open"] == 1]
    df = df.copy()
    df["popularity"] = df["popularity"].fillna(0.0)
    return df


def _parse_intent(text: str) -> ParsedIntent:
    normalized = text.lower()
    categories: set[str] = set()
    attributes: set[str] = set()

    for phrase, column in CATEGORY_KEYWORDS.items():
        if phrase in normalized:
            categories.add(column)
    for phrase, column in ATTRIBUTE_KEYWORDS.items():
        if phrase in normalized:
            attributes.add(column)

    require_parking = any(word in normalized for word in ["parking", "park", "car park"])
    require_late_night = "late" in normalized or "late night" in normalized
    require_burgers = "burger" in normalized or "burgers" in normalized

    requested_results = _extract_requested_count(normalized)

    return ParsedIntent(
        categories=categories,
        require_late_night=require_late_night,
        require_parking=require_parking,
        require_burgers=require_burgers,
        attributes=attributes,
        requested_results=requested_results,
    )


def _extract_requested_count(text: str) -> int | None:
    match = re.search(r"\btop\s+(\d{1,2})\b", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d{1,2})\s+(?:places|results|options|bars|restaurants|spots)\b", text)
    if match:
        return int(match.group(1))
    return None


def _apply_filters(df: pd.DataFrame, intent: ParsedIntent) -> pd.DataFrame:
    candidates = df

    if intent.categories:
        masks = []
        for col in intent.categories:
            if col in candidates.columns:
                masks.append(candidates[col])
        if masks:
            combined = np.logical_or.reduce(masks)
            subset = candidates[combined]
            if not subset.empty:
                candidates = subset

    if intent.require_burgers and "cat_Burgers" in candidates.columns:
        candidates = candidates[candidates["cat_Burgers"]]

    for attr in intent.attributes:
        if attr in candidates.columns:
            candidates = candidates[candidates[attr] == True]  # noqa: E712

    if intent.require_parking:
        parking_cols = [col for col in PARKING_COLUMNS if col in candidates.columns]
        if parking_cols:
            parking_mask = np.logical_or.reduce([candidates[col] for col in parking_cols])
            candidates = candidates[parking_mask]

    if intent.require_late_night and "late_night" in candidates.columns:
        candidates = candidates[candidates["late_night"] == True]  # noqa: E712

    # Future-proof: city/country filters can be added here when columns become available.
    return candidates.dropna(subset=["latitude", "longitude"])


def _rank_candidates(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
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


def _normalize_requested_results(value: int | None) -> int:
    if value is None or value < 1:
        return 5
    if value > 10:
        return 10
    return value


def _build_map_url(lat: float, lon: float) -> str | None:
    if pd.isna(lat) or pd.isna(lon):
        return None
    return f"https://www.google.com/maps?q={lat},{lon}"


def _build_explanation(name: str, max_results: int, intent: ParsedIntent) -> str:
    base = f"Showing top {max_results} match" if max_results == 1 else f"Showing top {max_results} matches"
    if intent.requested_results and intent.requested_results > 10:
        return f"{base} (capped at 10)."
    return f"{base} including {name}."


__all__ = ["recommendation_tool"]
