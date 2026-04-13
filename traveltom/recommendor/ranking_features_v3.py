"""Step 2 ranking feature engineering for recommender_v3.

This module is intentionally ranker-agnostic:
- input: retrieval candidate pool + normalized request context
- output: numeric feature frame keyed by business_id
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

_ITEM_TYPE_TO_ENTITY_TYPES: dict[str, set[str]] = {
    "hotel": {"hotel"},
    "flight": {"flight"},
    "destination": {"attraction", "restaurant"},
}

_GEO_FIELDS = (
    "city_norm",
    "state_norm",
    "country_norm",
    "country_name_norm",
    "continent_norm",
)


@dataclass(frozen=True)
class RankingFeatureContext:
    normalized_query_text: str
    query_tokens: tuple[str, ...]
    category_terms: tuple[str, ...]
    entity_types: tuple[str, ...]
    requested_item_type: str | None
    city: str | None
    state: str | None
    country: str | None
    country_name: str | None
    continent: str | None
    destination_hint: str | None
    require_open: bool
    price_level_min: float | None
    price_level_max: float | None


@dataclass(frozen=True)
class RankingFeatureArtifacts:
    features: pd.DataFrame


RANKING_FEATURE_COLUMNS: tuple[str, ...] = (
    "business_id",
    "f_retrieval_score",
    "f_retrieval_text_match",
    "f_retrieval_category_match",
    "f_retrieval_geo_match",
    "f_retrieval_entity_type_match",
    "f_retrieval_price_match",
    "f_quality_stars",
    "f_quality_review_count",
    "f_quality_log_review_count",
    "f_quality_popularity",
    "f_quality_log_popularity",
    "f_rel_name_token_hits",
    "f_rel_category_token_hits",
    "f_rel_description_token_hits",
    "f_rel_query_phrase_in_name",
    "f_rel_query_phrase_in_description",
    "f_rel_query_token_coverage",
    "f_rel_text_overall",
    "f_align_category_term_hits",
    "f_align_category_term_coverage",
    "f_align_entity_type_constraint_present",
    "f_align_entity_type_match",
    "f_align_item_type_constraint_present",
    "f_align_item_type_match",
    "f_geo_city_match",
    "f_geo_state_match",
    "f_geo_country_match",
    "f_geo_country_name_match",
    "f_geo_continent_match",
    "f_geo_destination_match_count",
    "f_geo_any_match",
    "f_availability_is_open",
    "f_availability_open_requested_match",
    "f_price_level",
    "f_price_level_known",
    "f_price_within_range",
    "f_price_distance_from_range",
    "f_price_best_effort_match",
    "f_metadata_has_description",
    "f_metadata_has_website",
    "f_metadata_has_phone",
    "f_metadata_has_address",
    "f_metadata_has_coordinates",
    "f_metadata_completeness_score",
    "f_struct_description_char_len",
    "f_struct_description_token_count",
    "f_struct_category_count",
    "f_struct_source_known",
    "f_struct_missing_primary_text",
)


def build_ranking_features(
    *,
    context: RankingFeatureContext,
    candidates: pd.DataFrame,
) -> RankingFeatureArtifacts:
    """Build a stable ranking feature frame for retrieved candidates."""

    if candidates.empty:
        return RankingFeatureArtifacts(features=pd.DataFrame(columns=RANKING_FEATURE_COLUMNS))

    working = candidates.copy()
    working = _ensure_candidate_columns(working)

    features = pd.DataFrame(
        {
            "business_id": working["business_id"].astype("string").fillna("").astype(str),
        }
    )

    features["f_retrieval_score"] = _safe_numeric_series(working, "retrieval_score")
    features["f_retrieval_text_match"] = _safe_numeric_series(
        working,
        "retrieval_text_match",
    )
    features["f_retrieval_category_match"] = _safe_numeric_series(
        working,
        "retrieval_category_match",
    )
    features["f_retrieval_geo_match"] = _safe_numeric_series(working, "retrieval_geo_match")
    features["f_retrieval_entity_type_match"] = _safe_numeric_series(
        working,
        "retrieval_entity_type_match",
    )
    features["f_retrieval_price_match"] = _safe_numeric_series(
        working,
        "retrieval_price_match",
    )

    stars = _safe_numeric_series(working, "stars")
    review_count = _safe_numeric_series(working, "review_count")
    popularity = _safe_numeric_series(working, "popularity")

    features["f_quality_stars"] = stars
    features["f_quality_review_count"] = review_count
    features["f_quality_log_review_count"] = np.log1p(review_count)
    features["f_quality_popularity"] = popularity
    features["f_quality_log_popularity"] = np.log1p(popularity.clip(lower=0))

    name_norm = _safe_text_series(working, "name_norm")
    categories_norm = _safe_text_series(working, "categories_norm")
    description_norm = _safe_text_series(working, "description_norm")

    name_hits = _token_match_count(name_norm, context.query_tokens)
    category_hits = _token_match_count(categories_norm, context.query_tokens)
    description_hits = _token_match_count(description_norm, context.query_tokens)

    features["f_rel_name_token_hits"] = name_hits
    features["f_rel_category_token_hits"] = category_hits
    features["f_rel_description_token_hits"] = description_hits
    features["f_rel_query_phrase_in_name"] = _phrase_presence(
        name_norm,
        context.normalized_query_text,
    )
    features["f_rel_query_phrase_in_description"] = _phrase_presence(
        description_norm,
        context.normalized_query_text,
    )
    query_token_count = float(max(1, len(context.query_tokens)))
    features["f_rel_query_token_coverage"] = (
        (name_hits + category_hits + description_hits) / query_token_count
    )
    features["f_rel_text_overall"] = (
        1.8 * name_hits + 1.4 * category_hits + 1.0 * description_hits
    )

    category_term_hits = _token_match_count(categories_norm, context.category_terms)
    features["f_align_category_term_hits"] = category_term_hits
    category_term_count = float(max(1, len(context.category_terms)))
    features["f_align_category_term_coverage"] = category_term_hits / category_term_count

    entity_type_norm = _safe_text_series(working, "entity_type_norm")
    entity_constraint_present = 1.0 if context.entity_types else 0.0
    features["f_align_entity_type_constraint_present"] = entity_constraint_present
    if context.entity_types:
        entity_match = entity_type_norm.isin(context.entity_types)
    else:
        entity_match = pd.Series(np.zeros(len(working), dtype=bool), index=working.index)
    features["f_align_entity_type_match"] = entity_match.astype(np.float32)

    requested_item_types = (
        _ITEM_TYPE_TO_ENTITY_TYPES.get(context.requested_item_type)
        if context.requested_item_type is not None
        else None
    )
    item_type_constraint_present = 1.0 if requested_item_types else 0.0
    features["f_align_item_type_constraint_present"] = item_type_constraint_present
    if requested_item_types:
        item_type_match = entity_type_norm.isin(requested_item_types)
    else:
        item_type_match = pd.Series(np.zeros(len(working), dtype=bool), index=working.index)
    features["f_align_item_type_match"] = item_type_match.astype(np.float32)

    city_match = _field_match_feature(_safe_text_series(working, "city_norm"), context.city)
    state_match = _field_match_feature(
        _safe_text_series(working, "state_norm"),
        context.state,
    )
    country_match = _field_match_feature(
        _safe_text_series(working, "country_norm"),
        context.country,
    )
    country_name_match = _field_match_feature(
        _safe_text_series(working, "country_name_norm"),
        context.country_name,
    )
    continent_match = _field_match_feature(
        _safe_text_series(working, "continent_norm"),
        context.continent,
    )

    features["f_geo_city_match"] = city_match
    features["f_geo_state_match"] = state_match
    features["f_geo_country_match"] = country_match
    features["f_geo_country_name_match"] = country_name_match
    features["f_geo_continent_match"] = continent_match

    if context.destination_hint:
        destination_match_count = np.zeros(len(working), dtype=np.float32)
        for field in _GEO_FIELDS:
            field_match = _field_match_feature(
                _safe_text_series(working, field),
                context.destination_hint,
            )
            destination_match_count += field_match
    else:
        destination_match_count = np.zeros(len(working), dtype=np.float32)

    features["f_geo_destination_match_count"] = destination_match_count

    features["f_geo_any_match"] = np.maximum.reduce(
        [
            city_match,
            state_match,
            country_match,
            country_name_match,
            continent_match,
            (destination_match_count > 0).astype(np.float32),
        ]
    )

    is_open = _safe_numeric_series(working, "is_open")
    is_open_binary = (is_open >= 1).astype(np.float32)
    features["f_availability_is_open"] = is_open_binary
    if context.require_open:
        features["f_availability_open_requested_match"] = is_open_binary
    else:
        features["f_availability_open_requested_match"] = np.ones(
            len(working),
            dtype=np.float32,
        )

    price_level = _safe_numeric_series(working, "price_level")
    price_known = (~working["price_level"].isna()).astype(np.float32)
    price_within_range, price_distance = _price_range_features(price_level, context)

    features["f_price_level"] = price_level
    features["f_price_level_known"] = price_known
    features["f_price_within_range"] = price_within_range
    features["f_price_distance_from_range"] = price_distance
    if context.price_level_min is None and context.price_level_max is None:
        features["f_price_best_effort_match"] = np.where(price_known > 0, 1.0, 0.75)
    else:
        features["f_price_best_effort_match"] = np.where(
            price_known > 0,
            price_within_range,
            0.5,
        )

    has_description = _non_empty_text_indicator(working, "description")
    has_website = _non_empty_text_indicator(working, "website")
    has_phone = _non_empty_text_indicator(working, "phone")
    has_address = _non_empty_text_indicator(working, "address")
    has_coordinates = (
        (~working["latitude"].isna()) & (~working["longitude"].isna())
    ).astype(np.float32)

    features["f_metadata_has_description"] = has_description
    features["f_metadata_has_website"] = has_website
    features["f_metadata_has_phone"] = has_phone
    features["f_metadata_has_address"] = has_address
    features["f_metadata_has_coordinates"] = has_coordinates
    features["f_metadata_completeness_score"] = (
        has_description
        + has_website
        + has_phone
        + has_address
        + has_coordinates
    ) / 5.0

    description_raw = _safe_text_series(working, "description")
    features["f_struct_description_char_len"] = description_raw.str.len().astype(np.float32)
    features["f_struct_description_token_count"] = (
        description_raw.str.split().str.len().fillna(0).astype(np.float32)
    )
    features["f_struct_category_count"] = _category_count_feature(working)
    features["f_struct_source_known"] = _non_empty_text_indicator(working, "source")
    features["f_struct_missing_primary_text"] = (
        (1 - has_description)
        * (features["f_struct_category_count"] <= 0).astype(np.float32)
    )

    features = _finalize_feature_frame(features)
    return RankingFeatureArtifacts(features=features)


def _ensure_candidate_columns(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()

    for column in (
        "business_id",
        "name_norm",
        "categories_norm",
        "description_norm",
        "entity_type_norm",
        "city_norm",
        "state_norm",
        "country_norm",
        "country_name_norm",
        "continent_norm",
        "description",
        "website",
        "phone",
        "address",
        "source",
        "categories",
    ):
        if column not in working.columns:
            working[column] = ""

    for column in (
        "stars",
        "review_count",
        "popularity",
        "retrieval_score",
        "retrieval_text_match",
        "retrieval_category_match",
        "retrieval_geo_match",
        "retrieval_entity_type_match",
        "retrieval_price_match",
        "is_open",
        "price_level",
        "latitude",
        "longitude",
    ):
        if column not in working.columns:
            working[column] = np.nan

    return working


def _safe_text_series(df: pd.DataFrame, column: str) -> pd.Series:
    return (
        df[column]
        .astype("string")
        .fillna("")
        .astype(str)
        .str.strip()
    )


def _safe_numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0).astype(np.float32)


def _token_match_count(series: pd.Series, tokens: Iterable[str]) -> pd.Series:
    token_list = [token for token in tokens if token]
    if not token_list:
        return pd.Series(np.zeros(len(series), dtype=np.float32), index=series.index)

    counts = np.zeros(len(series), dtype=np.float32)
    for token in token_list:
        pattern = rf"\b{re.escape(token)}\b"
        counts += series.str.contains(pattern, regex=True, na=False).to_numpy(dtype=np.float32)

    return pd.Series(counts, index=series.index, dtype=np.float32)


def _phrase_presence(series: pd.Series, phrase: str) -> pd.Series:
    if not phrase:
        return pd.Series(np.zeros(len(series), dtype=np.float32), index=series.index)
    pattern = rf"\b{re.escape(phrase)}\b"
    return series.str.contains(pattern, regex=True, na=False).astype(np.float32)


def _field_match_feature(series: pd.Series, value: str | None) -> np.ndarray:
    if value is None:
        return np.zeros(len(series), dtype=np.float32)

    mask = np.zeros(len(series), dtype=bool)
    for variant in _location_variants(value):
        pattern = rf"\b{re.escape(variant)}\b"
        mask |= series.str.contains(pattern, regex=True, na=False).to_numpy(dtype=bool)

    return mask.astype(np.float32)


def _location_variants(value: str) -> set[str]:
    normalized = value.strip().lower()
    if not normalized:
        return set()

    variants = {normalized}
    if normalized.startswith("st "):
        variants.add("saint " + normalized[3:])
    if normalized.startswith("saint "):
        variants.add("st " + normalized[6:])
    return {item.strip() for item in variants if item.strip()}


def _price_range_features(
    price_level: pd.Series,
    context: RankingFeatureContext,
) -> tuple[np.ndarray, np.ndarray]:
    if context.price_level_min is None and context.price_level_max is None:
        zeros = np.zeros(len(price_level), dtype=np.float32)
        return zeros, zeros

    values = price_level.to_numpy(dtype=np.float32)
    missing = np.isnan(values)

    within = np.ones(len(values), dtype=bool)
    distance = np.zeros(len(values), dtype=np.float32)

    if context.price_level_min is not None:
        below = values < context.price_level_min
        within &= ~below
        distance += np.where(
            below,
            context.price_level_min - values,
            0.0,
        ).astype(np.float32)

    if context.price_level_max is not None:
        above = values > context.price_level_max
        within &= ~above
        distance += np.where(
            above,
            values - context.price_level_max,
            0.0,
        ).astype(np.float32)

    within = np.where(missing, False, within)
    distance = np.where(missing, 0.0, distance)

    return within.astype(np.float32), distance.astype(np.float32)


def _non_empty_text_indicator(df: pd.DataFrame, column: str) -> pd.Series:
    values = _safe_text_series(df, column)
    return ((values != "") & (~values.str.lower().isin(["nan", "none"]))).astype(np.float32)


def _category_count_feature(df: pd.DataFrame) -> pd.Series:
    categories = _safe_text_series(df, "categories")
    split_values = categories.str.split(r"[;|/]", regex=True)

    return split_values.map(
        lambda values: float(sum(1 for value in values if str(value).strip()))
        if isinstance(values, list)
        else 0.0
    ).astype(np.float32)


def _finalize_feature_frame(features: pd.DataFrame) -> pd.DataFrame:
    final = features.copy()

    for column in RANKING_FEATURE_COLUMNS:
        if column not in final.columns:
            if column == "business_id":
                final[column] = ""
            else:
                final[column] = 0.0

    numeric_columns = [column for column in RANKING_FEATURE_COLUMNS if column != "business_id"]
    final[numeric_columns] = final[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    ).fillna(0.0)

    final = final[list(RANKING_FEATURE_COLUMNS)]
    return final


__all__ = [
    "RANKING_FEATURE_COLUMNS",
    "RankingFeatureArtifacts",
    "RankingFeatureContext",
    "build_ranking_features",
]
