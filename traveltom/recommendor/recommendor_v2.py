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
    if (
        requested is None
        and query.max_results is not None
        and 1 <= query.max_results <= 10
    ):
        requested = query.max_results
    max_results, limit_notice = _normalize_requested_results(requested)

    candidates = _apply_filters(catalog_df, intent)
    if candidates.empty:
        return RecommendationToolResponse(results=[], ranking_version=RANKING_VERSION)

    ranked = _rank_candidates(candidates)
    results: list[RecommendationResult] = []
    for rank, row in enumerate(
        ranked.head(max_results).itertuples(index=False), start=1
    ):
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
                explanation=_build_explanation(
                    row.name, max_results, limit_notice, intent
                ),
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
    df["weekly_open_minutes"] = df.get("weekly_open_minutes", 0).fillna(0)
    df["weekend_open_minutes"] = df.get("weekend_open_minutes", 0).fillna(0)
    return df


def _parse_intent(text: str) -> ParsedIntent:
    normalized = _normalize_text(text)
    tokens = _tokenize(normalized)

    categories = _match_categories(tokens, normalized)
    attributes = _match_attributes(tokens, normalized)

    require_parking = _has_phrase(normalized, ["parking", "car park", "garage parking"])
    require_late_night = _has_phrase(normalized, ["late night", "open late", "late"])
    require_burgers = "burger" in tokens or "burgers" in tokens
    price_tier = _detect_price(tokens)

    requested_results = _extract_requested_count(normalized)
    city = _extract_city(normalized)

    return ParsedIntent(
        categories=categories,
        require_late_night=require_late_night,
        require_parking=require_parking,
        require_burgers=require_burgers,
        attributes=attributes,
        price_tier=price_tier,
        requested_results=requested_results,
        city=city,
    )


def _extract_requested_count(text: str) -> int | None:
    match = re.search(r"\btop\s+(\d{1,2})\b", text)
    if match:
        return int(match.group(1))
    match = re.search(
        r"\b(\d{1,2})\s+(?:places|results|options|bars|restaurants|spots)\b", text
    )
    if match:
        return int(match.group(1))
    return None


def _extract_city(text: str) -> str | None:
    match = re.search(r"in ([a-zA-Z][a-zA-Z\\s]+)", text)
    if match:
        return match.group(1).strip()
    return None


def _apply_filters(df: pd.DataFrame, intent: ParsedIntent) -> pd.DataFrame:
    candidates = df

    if intent.categories:
        masks = []
        for col in intent.categories:
            if col in candidates.columns:
                masks.append(candidates[col])
        if "categories_list" in candidates.columns:
            for key in intent.categories:
                label = key.replace("cat_", "").replace("_", " ").lower()
                masks.append(
                    candidates["categories_list"]
                    .astype(str)
                    .str.lower()
                    .str.contains(label)
                )
        if "categories" in candidates.columns:
            for key in intent.categories:
                label = key.replace("cat_", "").replace("_", " ").lower()
                masks.append(
                    candidates["categories"].astype(str).str.lower().str.contains(label)
                )
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
            parking_mask = np.logical_or.reduce(
                [candidates[col] for col in parking_cols]
            )
            candidates = candidates[parking_mask]

    if intent.require_late_night and "late_night" in candidates.columns:
        candidates = candidates[candidates["late_night"] == True]  # noqa: E712

    if intent.price_tier and "attr_RestaurantsPriceRange2" in candidates.columns:
        if intent.price_tier == "low":
            candidates = candidates[
                candidates["attr_RestaurantsPriceRange2"].fillna(5) <= 2
            ]
        elif intent.price_tier == "high":
            candidates = candidates[
                candidates["attr_RestaurantsPriceRange2"].fillna(0) >= 3
            ]

    if intent.city and "city" in candidates.columns:
        city_mask = candidates["city"].astype(str).str.lower().str.contains(intent.city)
        subset = candidates[city_mask]
        if not subset.empty:
            candidates = subset

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
        + 0.05 * np.log1p(working.get("weekly_open_minutes", 0))
        + 0.02 * np.log1p(working.get("weekend_open_minutes", 0))
    )
    ranked = working.sort_values(
        by=["score", "review_count", "popularity", "business_id"],
        ascending=[False, False, False, True],
        kind="mergesort",
    )
    return ranked


def _normalize_requested_results(value: int | None) -> tuple[int, str | None]:
    if value is None or value < 1:
        return 5, None
    if value > 10:
        return 10, "You asked for more than 10 places. I can show up to 10."
    return value, None


def _build_map_url(lat: float, lon: float) -> str | None:
    if pd.isna(lat) or pd.isna(lon):
        return None
    return f"https://www.google.com/maps?q={lat},{lon}"


def _build_explanation(
    name: str, max_results: int, limit_notice: str | None, intent: ParsedIntent
) -> str:
    base = (
        f"Showing top {max_results} match"
        if max_results == 1
        else f"Showing top {max_results} matches"
    )
    notice = f"{limit_notice} " if limit_notice else ""
    return f"{notice}{base}, including {name}."


def _normalize_text(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower())


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[\w']+\b", text)


def _has_phrase(text: str, phrases: Sequence[str]) -> bool:
    return any(re.search(rf"\b{re.escape(p)}\b", text) for p in phrases)


def _match_categories(tokens: list[str], text: str) -> set[str]:
    categories: set[str] = set()
    for phrase, column in CATEGORY_KEYWORDS.items():
        if _has_phrase(text, [phrase]):
            categories.add(column)
    return categories


def _match_attributes(tokens: list[str], text: str) -> set[str]:
    attrs: set[str] = set()
    for phrase, column in ATTRIBUTE_KEYWORDS.items():
        if _has_phrase(text, [phrase]):
            attrs.add(column)
    return attrs


def _detect_price(tokens: list[str]) -> str | None:
    if any(
        t in tokens for t in ["cheap", "budget", "affordable", "inexpensive", "low"]
    ):
        return "low"
    if any(t in tokens for t in ["expensive", "fine", "premium", "high", "pricey"]):
        return "high"
    return None


__all__ = ["recommendation_tool"]
