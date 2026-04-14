"""Recommender v3 over the TravelTom clean CSV.

Current architecture:
1) schema-aware catalog preparation
2) structured/text candidate retrieval
3) explicit ranking feature engineering
4) pluggable ranking layer (heuristic or ML)
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)

from traveltom.recommendor.heuristic_ranker_v3 import HeuristicRankerV3
from traveltom.recommendor.ml_ranker_v3 import get_ml_ranker_from_env
from traveltom.recommendor.ranking_features_v3 import (
    RankingFeatureContext,
    build_ranking_features,
)

DATASET_NAME = "traveltom_clean.csv"
PIPELINE_VERSION = "recommender-v3"
HEURISTIC_RANKER = HeuristicRankerV3()
DEFAULT_RANKER_MODE = "heuristic"

_RESULT_ITEM_TYPE_BY_ENTITY_TYPE: dict[str, str] = {
    "hotel": "hotel",
    "flight": "flight",
}

_ITEM_TYPE_TO_ENTITY_TYPES: dict[str, set[str]] = {
    "hotel": {"hotel"},
    "flight": {"flight"},
    # Destination ideas should not be forced to hotels.
    "destination": {"attraction", "restaurant"},
}

_GEO_FIELDS = (
    "city_norm",
    "state_norm",
    "country_norm",
    "country_name_norm",
    "continent_norm",
)

_TEXT_FIELDS_FOR_SEARCH = (
    "name_norm",
    "categories_norm",
    "description_norm",
    "entity_type_norm",
    "city_norm",
    "state_norm",
    "country_norm",
    "country_name_norm",
    "continent_norm",
)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "at",
    "best",
    "find",
    "for",
    "from",
    "go",
    "ideas",
    "in",
    "is",
    "it",
    "like",
    "me",
    "near",
    "of",
    "on",
    "option",
    "options",
    "place",
    "places",
    "please",
    "recommend",
    "recommendation",
    "recommendations",
    "show",
    "suggest",
    "suggestions",
    "that",
    "the",
    "to",
    "trip",
    "travel",
    "vacation",
    "with",
}

_LOCATION_PHRASE_PATTERN = re.compile(
    r"\b(?:in|near|around|at)\s+"
    r"(?P<location>[a-zA-Z][a-zA-Z .'-]{1,80}?)"
    r"(?=(?:\s+(?:for|with|under|over|between|from|to|on|during|next|this|"
    r"budget|price|open|hotel|hotels|restaurant|restaurants|attraction|attractions)\b)"
    r"|[,.!?;]|$)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class RetrievalConfig:
    min_candidate_pool: int = 150
    pool_multiplier: int = 25
    max_candidate_pool: int = 3000
    max_query_tokens: int = 10


@dataclass(frozen=True)
class RetrievalRequest:
    normalized_query_text: str
    query_tokens: tuple[str, ...]
    category_terms: tuple[str, ...]
    entity_types: tuple[str, ...]
    city: str | None
    state: str | None
    country: str | None
    country_name: str | None
    continent: str | None
    destination_hint: str | None
    require_open: bool
    price_level_min: float | None
    price_level_max: float | None
    max_results: int
    requested_item_type: str | None


@dataclass(frozen=True)
class RetrievalArtifacts:
    candidates: pd.DataFrame


@dataclass(frozen=True)
class Stage1RankArtifacts:
    ranked: pd.DataFrame
    ranking_version: str


@dataclass(frozen=True)
class CandidateFeatureArtifacts:
    request: RetrievalRequest
    retrieval: RetrievalArtifacts
    feature_context: RankingFeatureContext
    features: pd.DataFrame


def recommendation_tool(
    query: RecommendationQuery,
    catalog: pd.DataFrame | None = None,
    *,
    catalog_prepared: bool = False,
) -> RecommendationToolResponse:
    """Return recommendations using retrieval-first v3 architecture."""

    ranker = _resolve_ranker(query)
    artifacts = build_candidate_feature_artifacts(
        query=query,
        catalog=catalog,
        catalog_prepared=catalog_prepared,
    )

    if artifacts.retrieval.candidates.empty:
        return RecommendationToolResponse(
            results=[],
            ranking_version=f"{PIPELINE_VERSION}:{ranker.version}",
        )
    if artifacts.features.empty:
        return RecommendationToolResponse(
            results=[],
            ranking_version=f"{PIPELINE_VERSION}:{ranker.version}",
        )

    ranking = _rank_candidates_stage1(
        retrieval=artifacts.retrieval,
        feature_frame=artifacts.features,
        feature_context=artifacts.feature_context,
        ranker=ranker,
    )
    if ranking.ranked.empty:
        return RecommendationToolResponse(
            results=[], ranking_version=ranking.ranking_version
        )

    return _build_response(
        ranking.ranked,
        artifacts.request,
        ranking_version=ranking.ranking_version,
    )


def build_candidate_feature_artifacts(
    *,
    query: RecommendationQuery,
    catalog: pd.DataFrame | None = None,
    catalog_prepared: bool = False,
) -> CandidateFeatureArtifacts:
    """Build request-normalized retrieval and ranking-feature artifacts."""

    request = _build_retrieval_request(query)
    feature_context = _build_feature_context(request)

    if catalog_prepared and catalog is not None:
        catalog_df = catalog
    else:
        catalog_df = prepare_catalog_for_v3(catalog=catalog)
    if catalog_df.empty:
        empty_features = build_ranking_features(
            context=feature_context,
            candidates=pd.DataFrame(),
        ).features
        return CandidateFeatureArtifacts(
            request=request,
            retrieval=RetrievalArtifacts(candidates=pd.DataFrame()),
            feature_context=feature_context,
            features=empty_features,
        )

    retrieval = _retrieve_candidates(catalog_df, request, RetrievalConfig())
    feature_artifacts = build_ranking_features(
        context=feature_context,
        candidates=retrieval.candidates,
    )
    return CandidateFeatureArtifacts(
        request=request,
        retrieval=retrieval,
        feature_context=feature_context,
        features=feature_artifacts.features,
    )


def prepare_catalog_for_v3(*, catalog: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return normalized catalog frame used by recommender_v3."""

    if catalog is None:
        return _load_prepared_catalog()
    return _prepare_catalog(catalog)


def is_catalog_prepared_for_v3() -> bool:
    """Return whether the default catalog has already been normalized and cached."""

    return _load_prepared_catalog.cache_info().currsize > 0


@lru_cache()
def _load_prepared_catalog() -> pd.DataFrame:
    return _prepare_catalog(_load_catalog())


@lru_cache()
def _load_catalog() -> pd.DataFrame:
    dataset_path = Path(__file__).parent.parent / "datasets" / DATASET_NAME
    if not dataset_path.exists():
        return pd.DataFrame()

    raw = pd.read_csv(
        dataset_path,
        low_memory=False,
        dtype={
            "business_id": "string",
            "name": "string",
            "city": "string",
            "state": "string",
            "country": "string",
            "country_name": "string",
            "continent": "string",
            "categories": "string",
            "attributes": "string",
            "hours": "string",
            "address": "string",
            "description": "string",
            "website": "string",
            "phone": "string",
            "source": "string",
            "entity_type": "string",
        },
    )
    return raw


def _prepare_catalog(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    df = _canonicalize_catalog_schema(raw.copy())

    for column in (
        "business_id",
        "name",
        "city",
        "state",
        "country",
        "country_name",
        "continent",
        "categories",
        "description",
        "source",
        "entity_type",
        "address",
        "website",
        "phone",
    ):
        if column not in df.columns:
            df[column] = ""

    for column in (
        "latitude",
        "longitude",
        "stars",
        "review_count",
        "price_level",
        "popularity",
    ):
        if column not in df.columns:
            df[column] = np.nan

    if "is_open" not in df.columns:
        df["is_open"] = 1

    for column in (
        "business_id",
        "name",
        "city",
        "state",
        "country",
        "country_name",
        "continent",
        "categories",
        "description",
        "source",
        "entity_type",
        "address",
        "website",
        "phone",
    ):
        df[column] = df[column].astype("string").fillna("")

    for column in (
        "latitude",
        "longitude",
        "stars",
        "review_count",
        "price_level",
        "popularity",
    ):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["is_open"] = pd.to_numeric(df["is_open"], errors="coerce").fillna(1).astype(int)
    df["stars"] = df["stars"].fillna(0.0)
    df["review_count"] = df["review_count"].fillna(0).astype(int)
    df["popularity"] = df["popularity"].fillna(0.0)

    df["name_norm"] = df["name"].map(_normalize_text)
    df["city_norm"] = df["city"].map(_normalize_text)
    df["state_norm"] = df["state"].map(_normalize_text)
    df["country_norm"] = df["country"].map(_normalize_text)
    df["country_name_norm"] = df["country_name"].map(_normalize_text)
    df["continent_norm"] = df["continent"].map(_normalize_text)
    df["entity_type_norm"] = df["entity_type"].map(_normalize_text)
    df["categories_norm"] = df["categories"].map(_normalize_categories)
    df["description_norm"] = df["description"].map(_normalize_text)

    search_parts = [df[field] for field in _TEXT_FIELDS_FOR_SEARCH]
    df["search_text_norm"] = (
        pd.concat(search_parts, axis=1)
        .astype("string")
        .fillna("")
        .agg(" ".join, axis=1)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # Useful later for optional location exact matching features.
    df["geo_blob_norm"] = (
        df["city_norm"]
        + " "
        + df["state_norm"]
        + " "
        + df["country_norm"]
        + " "
        + df["country_name_norm"]
        + " "
        + df["continent_norm"]
    ).str.replace(r"\s+", " ", regex=True)

    return df


def _canonicalize_catalog_schema(raw: pd.DataFrame) -> pd.DataFrame:
    working = raw.copy()
    row_count = len(working)

    def _series(name: str) -> pd.Series:
        if name in working.columns:
            return working[name]
        return pd.Series([np.nan] * row_count, index=working.index)

    name_series = _series("name").astype("string").fillna("")
    city_series = _series("city").astype("string").fillna("")
    country_series = _series("country").astype("string").fillna("")

    if "business_id" not in working.columns:
        working["business_id"] = _build_synthetic_business_ids(
            name_series=name_series,
            city_series=city_series,
            country_series=country_series,
            index=working.index,
        )
    else:
        business_id = _series("business_id").astype("string").fillna("").str.strip()
        missing_business_id = business_id.eq("")
        if missing_business_id.any():
            synthetic_ids = _build_synthetic_business_ids(
                name_series=name_series,
                city_series=city_series,
                country_series=country_series,
                index=working.index,
            )
            business_id = business_id.where(~missing_business_id, synthetic_ids)
        working["business_id"] = business_id

    if "categories" not in working.columns and "categories_clean" in working.columns:
        working["categories"] = _series("categories_clean")

    if "description" not in working.columns and "description_clean" in working.columns:
        working["description"] = _series("description_clean")
    elif "description_clean" in working.columns:
        description = _series("description").astype("string")
        description_clean = _series("description_clean").astype("string")
        working["description"] = description.where(
            description.fillna("").str.strip().ne(""),
            description_clean,
        )

    if "entity_type" not in working.columns:
        working["entity_type"] = _derive_entity_type_series(working)
    else:
        entity_type = _series("entity_type").astype("string").fillna("").str.strip()
        missing_entity_type = entity_type.eq("")
        if missing_entity_type.any():
            derived = _derive_entity_type_series(working)
            entity_type = entity_type.where(~missing_entity_type, derived)
        working["entity_type"] = entity_type

    if "source" not in working.columns:
        working["source"] = _derive_source_series(working)
    else:
        source = _series("source").astype("string").fillna("").str.strip()
        missing_source = source.eq("")
        if missing_source.any():
            derived_source = _derive_source_series(working)
            source = source.where(~missing_source, derived_source)
        working["source"] = source

    if "stars" not in working.columns and "stars_norm" in working.columns:
        working["stars"] = _rescale_series(
            pd.to_numeric(_series("stars_norm"), errors="coerce"),
            minimum=0.0,
            maximum=5.0,
        )

    if "review_count" not in working.columns and "review_count_norm" in working.columns:
        review_scaled = _rescale_series(
            pd.to_numeric(_series("review_count_norm"), errors="coerce"),
            minimum=0.0,
            maximum=1000.0,
        )
        working["review_count"] = np.round(review_scaled).astype("Int64")

    if "popularity" not in working.columns:
        if "popularity_norm" in working.columns:
            working["popularity"] = _rescale_series(
                pd.to_numeric(_series("popularity_norm"), errors="coerce"),
                minimum=0.0,
                maximum=10.0,
            )
        elif "quality_score" in working.columns:
            working["popularity"] = _rescale_series(
                pd.to_numeric(_series("quality_score"), errors="coerce"),
                minimum=0.0,
                maximum=10.0,
            )

    if "country_name" not in working.columns and "country" in working.columns:
        working["country_name"] = _series("country")

    return working


def _build_synthetic_business_ids(
    *,
    name_series: pd.Series,
    city_series: pd.Series,
    country_series: pd.Series,
    index: pd.Index,
) -> pd.Series:
    seed = (
        name_series.astype("string").fillna("")
        + "|"
        + city_series.astype("string").fillna("")
        + "|"
        + country_series.astype("string").fillna("")
        + "|"
        + index.astype(str)
    )
    return seed.map(_stable_business_id).astype("string")


def _stable_business_id(seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return f"tt-{digest[:16]}"


def _derive_entity_type_series(df: pd.DataFrame) -> pd.Series:
    index = df.index
    hotel = _coerce_flag_series(df, "entity_type_hotel")
    flight = _coerce_flag_series(df, "entity_type_flight")
    restaurant = _coerce_flag_series(df, "entity_type_restaurant")
    attraction = _coerce_flag_series(df, "entity_type_attraction")

    values = np.select(
        [
            flight.to_numpy(dtype=bool),
            hotel.to_numpy(dtype=bool),
            restaurant.to_numpy(dtype=bool),
            attraction.to_numpy(dtype=bool),
        ],
        ["flight", "hotel", "restaurant", "attraction"],
        default="destination",
    )
    return pd.Series(values, index=index, dtype="string")


def _derive_source_series(df: pd.DataFrame) -> pd.Series:
    index = df.index
    tbo_hotels = _coerce_flag_series(df, "source_tbo_hotels")
    tripadvisor = _coerce_flag_series(df, "source_tripadvisor")
    openstreetmap = _coerce_flag_series(df, "source_openstreetmap")

    values = np.select(
        [
            tbo_hotels.to_numpy(dtype=bool),
            tripadvisor.to_numpy(dtype=bool),
            openstreetmap.to_numpy(dtype=bool),
        ],
        ["tbo_hotels", "tripadvisor", "openstreetmap"],
        default="",
    )
    return pd.Series(values, index=index, dtype="string")


def _coerce_flag_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.zeros(len(df), dtype=bool), index=df.index)
    numeric = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return numeric.astype(float) > 0


def _rescale_series(
    series: pd.Series,
    *,
    minimum: float,
    maximum: float,
) -> pd.Series:
    cleaned = pd.to_numeric(series, errors="coerce")
    if cleaned.notna().sum() == 0:
        return pd.Series(np.nan, index=series.index)

    low = float(cleaned.min(skipna=True))
    high = float(cleaned.max(skipna=True))
    if math.isclose(low, high):
        midpoint = minimum + (maximum - minimum) / 2.0
        return pd.Series(midpoint, index=series.index)

    scaled = (cleaned - low) / (high - low)
    return minimum + scaled * (maximum - minimum)


def _build_retrieval_request(query: RecommendationQuery) -> RetrievalRequest:
    normalized_query_text = _normalize_text(query.query)
    requested_item_type = _normalize_item_type(query.filters.get("item_type"))

    entity_types = _parse_entity_type_filters(query.filters)
    if not entity_types and requested_item_type in _ITEM_TYPE_TO_ENTITY_TYPES:
        entity_types = set(_ITEM_TYPE_TO_ENTITY_TYPES[requested_item_type])

    city = _normalize_optional_text(query.filters.get("city"))
    state = _normalize_optional_text(query.filters.get("state"))
    country = _normalize_optional_text(query.filters.get("country"))
    country_name = _normalize_optional_text(query.filters.get("country_name"))
    continent = _normalize_optional_text(query.filters.get("continent"))

    destination_from_constraints = _normalize_optional_text(
        query.constraints.destination
    )
    destination_from_filters = _normalize_optional_text(
        query.filters.get("destination")
    )
    destination_from_text = _extract_location_from_query_text(normalized_query_text)
    destination_hint = (
        destination_from_constraints
        or destination_from_filters
        or destination_from_text
    )

    query_tokens = tuple(
        _extract_query_tokens(normalized_query_text)[
            : RetrievalConfig().max_query_tokens
        ]
    )
    category_terms = tuple(_extract_category_terms(query, query_tokens))

    require_open = _coerce_bool(query.filters.get("is_open"), default=True)

    price_level_min = _coerce_float(query.filters.get("price_level_min"))
    price_level_max = _coerce_float(query.filters.get("price_level_max"))
    exact_price = _coerce_float(query.filters.get("price_level"))
    if exact_price is not None:
        price_level_min = exact_price
        price_level_max = exact_price
    if price_level_max is None:
        price_level_max = _derive_price_level_max_from_budget(query)

    if query.max_results < 1:
        max_results = 1
    elif query.max_results > 50:
        max_results = 50
    else:
        max_results = query.max_results

    return RetrievalRequest(
        normalized_query_text=normalized_query_text,
        query_tokens=query_tokens,
        category_terms=category_terms,
        entity_types=tuple(sorted(entity_types)),
        city=city,
        state=state,
        country=country,
        country_name=country_name,
        continent=continent,
        destination_hint=destination_hint,
        require_open=require_open,
        price_level_min=price_level_min,
        price_level_max=price_level_max,
        max_results=max_results,
        requested_item_type=requested_item_type,
    )


def _retrieve_candidates(
    catalog_df: pd.DataFrame,
    request: RetrievalRequest,
    config: RetrievalConfig,
) -> RetrievalArtifacts:
    if catalog_df.empty:
        return RetrievalArtifacts(candidates=pd.DataFrame())

    candidates = catalog_df

    if request.require_open and "is_open" in candidates.columns:
        candidates = candidates[candidates["is_open"] == 1]

    if request.entity_types:
        candidates = candidates[
            candidates["entity_type_norm"].isin(request.entity_types)
        ]
        if candidates.empty:
            return RetrievalArtifacts(candidates=candidates)

    candidates = _apply_geo_filters(candidates, request)
    if candidates.empty:
        return RetrievalArtifacts(candidates=candidates)

    candidates = candidates.copy()
    candidates["retrieval_price_match"] = _compute_price_match_feature(
        candidates, request
    )
    if request.price_level_min is not None or request.price_level_max is not None:
        price_strict_mask = _price_level_within_range(
            candidates["price_level"], request
        )
        if price_strict_mask.any():
            candidates = candidates[price_strict_mask]

    candidates["retrieval_category_match"] = _token_match_count(
        candidates["categories_norm"], request.category_terms
    )

    candidates["retrieval_text_match"] = _compute_text_match_feature(
        candidates, request
    )

    if request.category_terms and (candidates["retrieval_category_match"] > 0).any():
        candidates = candidates[candidates["retrieval_category_match"] > 0]

    if request.query_tokens and (candidates["retrieval_text_match"] > 0).any():
        candidates = candidates[candidates["retrieval_text_match"] > 0]

    if candidates.empty:
        return RetrievalArtifacts(candidates=candidates)

    candidates["retrieval_geo_match"] = _compute_geo_match_feature(candidates, request)
    candidates["retrieval_entity_type_match"] = _compute_entity_type_match_feature(
        candidates,
        request,
    )
    candidates["retrieval_open_match"] = np.where(candidates["is_open"] == 1, 1.0, 0.0)

    candidates["retrieval_score"] = (
        2.8 * candidates["retrieval_entity_type_match"]
        + 2.2 * candidates["retrieval_geo_match"]
        + 1.6 * candidates["retrieval_category_match"]
        + 1.2 * candidates["retrieval_text_match"]
        + 0.3 * candidates["retrieval_open_match"]
        + 0.2 * candidates["retrieval_price_match"]
    )

    candidate_pool_size = min(
        config.max_candidate_pool,
        max(config.min_candidate_pool, request.max_results * config.pool_multiplier),
    )

    candidates = candidates.sort_values(
        by=["retrieval_score", "popularity", "review_count", "stars", "business_id"],
        ascending=[False, False, False, False, True],
        kind="mergesort",
    ).head(candidate_pool_size)

    return RetrievalArtifacts(candidates=candidates)


def _rank_candidates_stage1(
    *,
    retrieval: RetrievalArtifacts,
    feature_frame: pd.DataFrame,
    feature_context: RankingFeatureContext,
    ranker: Any,
) -> Stage1RankArtifacts:
    ranker_output = ranker.score(features=feature_frame, context=feature_context)

    ranked = retrieval.candidates.copy().merge(
        ranker_output.scored,
        on="business_id",
        how="inner",
    )
    if ranked.empty:
        return Stage1RankArtifacts(
            ranked=ranked,
            ranking_version=f"{PIPELINE_VERSION}:{ranker_output.version}",
        )

    ranked = ranked.sort_values(
        by=[
            "score_final",
            "score_relevance",
            "score_alignment",
            "f_quality_stars",
            "f_quality_review_count",
            "business_id",
        ],
        ascending=[False, False, False, False, False, True],
        kind="mergesort",
    )

    return Stage1RankArtifacts(
        ranked=ranked,
        ranking_version=f"{PIPELINE_VERSION}:{ranker_output.version}",
    )


def _resolve_ranker(query: RecommendationQuery) -> Any:
    mode = _resolve_ranker_mode(query)
    if mode == "ml":
        return get_ml_ranker_from_env()
    return HEURISTIC_RANKER


def _resolve_ranker_mode(query: RecommendationQuery) -> str:
    requested_mode = _mode_from_ranking_version(query.ranking_version)
    if requested_mode is not None:
        return requested_mode

    env_mode = _normalize_text(os.getenv("TRAVELTOM_RANKER_MODE", DEFAULT_RANKER_MODE))
    if env_mode in {"heuristic", "ml"}:
        return env_mode
    if env_mode == "auto":
        return "ml"
    return DEFAULT_RANKER_MODE


def _mode_from_ranking_version(ranking_version: str | None) -> str | None:
    normalized = _normalize_text(ranking_version)
    if not normalized:
        return None
    if any(token in normalized for token in ("ml", "lgbm", "lightgbm", "ltr")):
        return "ml"
    if "heuristic" in normalized:
        return "heuristic"
    return None


def _build_feature_context(request: RetrievalRequest) -> RankingFeatureContext:
    return RankingFeatureContext(
        normalized_query_text=request.normalized_query_text,
        query_tokens=request.query_tokens,
        category_terms=request.category_terms,
        entity_types=request.entity_types,
        requested_item_type=request.requested_item_type,
        city=request.city,
        state=request.state,
        country=request.country,
        country_name=request.country_name,
        continent=request.continent,
        destination_hint=request.destination_hint,
        require_open=request.require_open,
        price_level_min=request.price_level_min,
        price_level_max=request.price_level_max,
    )


def _build_response(
    ranked: pd.DataFrame,
    request: RetrievalRequest,
    *,
    ranking_version: str,
) -> RecommendationToolResponse:
    results: list[RecommendationResult] = []

    for rank, row in enumerate(
        ranked.head(request.max_results).itertuples(index=False), start=1
    ):
        entity_type = _normalize_text(getattr(row, "entity_type", ""))
        item_type = _RESULT_ITEM_TYPE_BY_ENTITY_TYPE.get(entity_type, "destination")

        features: dict[str, Any] = {
            "name": getattr(row, "name", ""),
            "city": getattr(row, "city", ""),
            "state": getattr(row, "state", ""),
            "country": getattr(row, "country", ""),
            "continent": getattr(row, "continent", ""),
            "entity_type": getattr(row, "entity_type", ""),
            "source": getattr(row, "source", ""),
        }

        map_url = _build_map_url(
            getattr(row, "latitude", np.nan), getattr(row, "longitude", np.nan)
        )
        if map_url is not None:
            features["map_url"] = map_url

        website = _clean_raw_text(getattr(row, "website", ""))
        if website:
            features["website"] = website

        price_level = getattr(row, "price_level", np.nan)
        if not pd.isna(price_level):
            features["price_level"] = float(price_level)

        explanation = _build_explanation(row)

        results.append(
            RecommendationResult(
                item_id=str(getattr(row, "business_id", "")),
                item_type=item_type,
                score=float(getattr(row, "score_final", 0.0)),
                rank=rank,
                features=features,
                explanation=explanation,
            )
        )

    return RecommendationToolResponse(results=results, ranking_version=ranking_version)


def _apply_geo_filters(
    candidates: pd.DataFrame, request: RetrievalRequest
) -> pd.DataFrame:
    filtered = candidates

    explicit_filters = (
        ("city_norm", request.city),
        ("state_norm", request.state),
        ("country_norm", request.country),
        ("country_name_norm", request.country_name),
        ("continent_norm", request.continent),
    )

    for column, value in explicit_filters:
        if value is None:
            continue
        mask = _location_match_series(filtered[column], value)
        filtered = filtered[mask]
        if filtered.empty:
            return filtered

    if request.destination_hint is None:
        return filtered

    destination_mask = np.zeros(len(filtered), dtype=bool)
    for field in _GEO_FIELDS:
        destination_mask |= _location_match_series(
            filtered[field], request.destination_hint
        )

    if destination_mask.any():
        return filtered[destination_mask]

    return filtered.iloc[0:0]


def _compute_entity_type_match_feature(
    candidates: pd.DataFrame,
    request: RetrievalRequest,
) -> pd.Series:
    if not request.entity_types:
        return pd.Series(
            np.ones(len(candidates), dtype=np.float32), index=candidates.index
        )

    return pd.Series(
        np.where(candidates["entity_type_norm"].isin(request.entity_types), 1.0, 0.0),
        index=candidates.index,
        dtype=np.float32,
    )


def _compute_geo_match_feature(
    candidates: pd.DataFrame, request: RetrievalRequest
) -> pd.Series:
    score = np.zeros(len(candidates), dtype=np.float32)

    for field, value in (
        ("city_norm", request.city),
        ("state_norm", request.state),
        ("country_norm", request.country),
        ("country_name_norm", request.country_name),
        ("continent_norm", request.continent),
    ):
        if value is None:
            continue
        score += _location_match_series(candidates[field], value).to_numpy(
            dtype=np.float32
        )

    if request.destination_hint:
        destination_match = np.zeros(len(candidates), dtype=bool)
        for field in _GEO_FIELDS:
            destination_match |= _location_match_series(
                candidates[field], request.destination_hint
            )
        score += destination_match.astype(np.float32)

    return pd.Series(score, index=candidates.index, dtype=np.float32)


def _compute_price_match_feature(
    candidates: pd.DataFrame, request: RetrievalRequest
) -> pd.Series:
    has_price = candidates["price_level"].notna()
    within_range = _price_level_within_range(candidates["price_level"], request)

    if request.price_level_min is None and request.price_level_max is None:
        return pd.Series(
            np.where(has_price, 1.0, 0.8), index=candidates.index, dtype=np.float32
        )

    # Best effort with sparse price_level: unknown values are not dropped by default.
    score = np.where(within_range, 1.0, 0.0)
    score = np.where(~has_price, 0.35, score)
    return pd.Series(score, index=candidates.index, dtype=np.float32)


def _compute_text_match_feature(
    candidates: pd.DataFrame, request: RetrievalRequest
) -> pd.Series:
    if not request.query_tokens:
        return pd.Series(
            np.zeros(len(candidates), dtype=np.float32), index=candidates.index
        )

    name_hits = _token_match_count(candidates["name_norm"], request.query_tokens)
    category_hits = _token_match_count(
        candidates["categories_norm"], request.query_tokens
    )
    full_text_hits = _token_match_count(
        candidates["search_text_norm"], request.query_tokens
    )

    # Keep this retrieval oriented and interpretable.
    text_score = 1.8 * name_hits + 1.4 * category_hits + 1.0 * full_text_hits
    return text_score.astype(np.float32)


def _price_level_within_range(
    series: pd.Series, request: RetrievalRequest
) -> pd.Series:
    working = pd.Series(np.ones(len(series), dtype=bool), index=series.index)
    if request.price_level_min is not None:
        working &= series.fillna(request.price_level_min) >= request.price_level_min
    if request.price_level_max is not None:
        working &= series.fillna(request.price_level_max) <= request.price_level_max
    return working


def _token_match_count(series: pd.Series, tokens: Iterable[str]) -> pd.Series:
    token_list = [token for token in tokens if token]
    if not token_list:
        return pd.Series(np.zeros(len(series), dtype=np.float32), index=series.index)

    score = np.zeros(len(series), dtype=np.float32)
    for token in token_list:
        pattern = rf"\b{re.escape(token)}\b"
        score += series.str.contains(pattern, regex=True, na=False).to_numpy(
            dtype=np.float32
        )

    return pd.Series(score, index=series.index, dtype=np.float32)


def _build_explanation(row: Any) -> str:
    reasons: list[str] = []
    if getattr(row, "retrieval_geo_match", 0.0) > 0:
        reasons.append("location")
    if getattr(row, "retrieval_entity_type_match", 0.0) > 0:
        reasons.append("entity type")
    if getattr(row, "retrieval_category_match", 0.0) > 0:
        reasons.append("category")
    if getattr(row, "retrieval_text_match", 0.0) > 0:
        reasons.append("text relevance")
    if getattr(row, "retrieval_price_match", 0.0) >= 1.0:
        reasons.append("price fit")

    name = getattr(row, "name", "this option")
    if reasons:
        summary = ", ".join(reasons[:3])
        return f"Matched by {summary}, including {name}."
    return f"Included from the candidate pool, including {name}."


def _build_map_url(latitude: float, longitude: float) -> str | None:
    if pd.isna(latitude) or pd.isna(longitude):
        return None
    return f"https://www.google.com/maps?q={latitude},{longitude}"


def _extract_query_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-z0-9][a-z0-9'-]*\b", text)
    filtered = [
        token
        for token in tokens
        if len(token) > 1 and token not in _STOPWORDS and not token.isdigit()
    ]

    seen: set[str] = set()
    unique_tokens: list[str] = []
    for token in filtered:
        if token in seen:
            continue
        unique_tokens.append(token)
        seen.add(token)

    return unique_tokens


def _extract_category_terms(
    query: RecommendationQuery, query_tokens: tuple[str, ...]
) -> list[str]:
    terms: set[str] = set()

    category_filter = query.filters.get("category")
    categories_filter = query.filters.get("categories")

    for value in _coerce_str_list(category_filter) + _coerce_str_list(
        categories_filter
    ):
        normalized = _normalize_text(value)
        if normalized:
            terms.update(_extract_query_tokens(normalized))

    terms.update(
        token
        for token in query_tokens
        if token not in {"hotel", "hotels", "flight", "flights"}
    )

    return sorted(terms)


def _extract_location_from_query_text(text: str) -> str | None:
    match = _LOCATION_PHRASE_PATTERN.search(text)
    if not match:
        return None
    return _normalize_optional_text(match.group("location"))


def _parse_entity_type_filters(filters: dict[str, Any]) -> set[str]:
    values = _coerce_str_list(filters.get("entity_type"))
    if not values and filters.get("entity_types") is not None:
        values = _coerce_str_list(filters.get("entity_types"))

    normalized: set[str] = set()
    for value in values:
        item = _normalize_text(value)
        if not item:
            continue
        if item.endswith("s") and len(item) > 3:
            item = item[:-1]
        normalized.add(item)
    return normalized


def _normalize_item_type(value: Any) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized.endswith("s") and len(normalized) > 3:
        normalized = normalized[:-1]
    if normalized in {"destination", "hotel", "flight"}:
        return normalized
    return None


def _derive_price_level_max_from_budget(query: RecommendationQuery) -> float | None:
    budget = query.constraints.budget
    if budget is None or budget.max is None:
        return None

    party_size = query.constraints.party_size
    travelers = 1
    if party_size is not None:
        travelers = max(1, party_size.adults + party_size.children)

    trip_days = 1
    if query.constraints.dates is not None:
        trip_days = max(
            1, (query.constraints.dates.end - query.constraints.dates.start).days + 1
        )

    per_person_daily_budget = budget.max / float(travelers * trip_days)
    if per_person_daily_budget <= 60:
        return 1.0
    if per_person_daily_budget <= 150:
        return 2.0
    if per_person_daily_budget <= 300:
        return 3.0
    return 4.0


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    return default


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = _normalize_text(str(value))
    return normalized or None


def _normalize_categories(value: Any) -> str:
    base = _normalize_text(value)
    if not base:
        return ""

    normalized = re.sub(r"[;|/]", " ", base)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _clean_raw_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    return text


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text or text.lower() in {"nan", "none"}:
        return ""

    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    lowered = ascii_text.lower()
    cleaned = re.sub(r"[^a-z0-9\s'-]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _location_match_series(series: pd.Series, value: str) -> pd.Series:
    variants = _location_variants(value)
    if not variants:
        return pd.Series(np.zeros(len(series), dtype=bool), index=series.index)

    mask = pd.Series(np.zeros(len(series), dtype=bool), index=series.index)
    for variant in variants:
        pattern = rf"\b{re.escape(variant)}\b"
        mask |= series.str.contains(pattern, regex=True, na=False)
    return mask


def _location_variants(value: str) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()

    variants = {normalized}
    if normalized.startswith("st "):
        variants.add("saint " + normalized[3:])
    if normalized.startswith("saint "):
        variants.add("st " + normalized[6:])
    return {item.strip() for item in variants if item.strip()}


__all__ = [
    "build_candidate_feature_artifacts",
    "is_catalog_prepared_for_v3",
    "prepare_catalog_for_v3",
    "recommendation_tool",
]
