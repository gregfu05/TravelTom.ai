"""Step 4 training-data pipeline for recommender_v3 ML ranking.

This module does not assume real interaction logs exist yet.
It supports:
- explicit judgment datasets (preferred when available)
- weak-supervision bootstrap labels for early-stage offline experiments
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from app.schemas.tools.recommendations import RecommendationQuery

from traveltom.recommendor.ml_ranker_v3 import ML_FEATURE_COLUMNS
from traveltom.recommendor.recommendor_v3 import (
    build_candidate_feature_artifacts,
    prepare_catalog_for_v3,
)
from traveltom.recommendor.ranking_features_v3 import RankingFeatureContext

LABEL_STRATEGY_EXPLICIT = "explicit-judgment-v1"
LABEL_STRATEGY_WEAK = "weak-supervision-v1"

_ITEM_TYPE_BY_ENTITY_TYPE: dict[str, str] = {
    "hotel": "hotel",
    "flight": "flight",
}

_IGNORED_CATEGORY_TERMS = {
    "and",
    "at",
    "bar",
    "food",
    "for",
    "in",
    "of",
    "place",
    "places",
    "restaurant",
    "restaurants",
    "shop",
    "the",
    "to",
}


@dataclass(frozen=True)
class RankerTrainingDataset:
    frame: pd.DataFrame
    feature_columns: tuple[str, ...]
    query_ids: tuple[str, ...]
    group_sizes: tuple[int, ...]
    label_strategy: str
    query_contexts: dict[str, RankingFeatureContext]


@dataclass(frozen=True)
class DatasetSplit:
    train: RankerTrainingDataset
    validation: RankerTrainingDataset


def build_training_dataset_from_judgments(
    *,
    judgments: pd.DataFrame,
    catalog: pd.DataFrame | None = None,
    max_candidates_per_query: int = 250,
    min_candidates_per_query: int = 2,
) -> RankerTrainingDataset:
    """Build grouped ranking data from explicit per-candidate labels.

    Required columns:
    - query_id
    - query
    - business_id
    - label

    Optional columns:
    - session_id
    - max_results
    - filters_json / filters
    - constraints_json / constraints
    """

    required = {"query_id", "query", "business_id", "label"}
    missing = required.difference(judgments.columns)
    if missing:
        raise ValueError(f"judgments missing required columns: {sorted(missing)}")

    if judgments.empty:
        return _empty_training_dataset(label_strategy=LABEL_STRATEGY_EXPLICIT)

    prepared_catalog = prepare_catalog_for_v3(catalog=catalog)
    if prepared_catalog.empty:
        return _empty_training_dataset(label_strategy=LABEL_STRATEGY_EXPLICIT)

    collected: list[pd.DataFrame] = []
    group_sizes: list[int] = []
    query_ids: list[str] = []
    query_contexts: dict[str, RankingFeatureContext] = {}

    normalized = judgments.copy()
    normalized["query_id"] = normalized["query_id"].astype(str)
    normalized["business_id"] = normalized["business_id"].astype(str)
    normalized["label"] = pd.to_numeric(normalized["label"], errors="coerce").fillna(0)

    for query_id, group in normalized.groupby("query_id", sort=True):
        request = _query_from_judgment_group(query_id=query_id, group=group)
        artifacts = build_candidate_feature_artifacts(
            query=request,
            catalog=prepared_catalog,
            catalog_prepared=True,
        )
        features = artifacts.features.copy()
        if features.empty:
            continue

        features = features.head(max_candidates_per_query)
        if len(features) < min_candidates_per_query:
            continue

        label_lookup = (
            group.groupby("business_id", sort=False)["label"]
            .max()
            .clip(lower=0)
            .to_dict()
        )
        labels = (
            features["business_id"]
            .map(label_lookup)
            .fillna(0)
            .astype(np.int32)
        )

        frame = features.copy()
        frame["query_id"] = str(query_id)
        frame["label"] = labels

        collected.append(frame)
        query_ids.append(str(query_id))
        group_sizes.append(len(frame))
        query_contexts[str(query_id)] = artifacts.feature_context

    return _finalize_training_dataset(
        frames=collected,
        query_ids=query_ids,
        group_sizes=group_sizes,
        label_strategy=LABEL_STRATEGY_EXPLICIT,
        query_contexts=query_contexts,
    )


def build_weak_supervision_training_dataset(
    *,
    catalog: pd.DataFrame | None = None,
    queries: Sequence[RecommendationQuery] | None = None,
    max_queries: int = 300,
    random_seed: int = 13,
    max_candidates_per_query: int = 250,
    min_candidates_per_query: int = 5,
) -> RankerTrainingDataset:
    """Build grouped ranking data using weak supervision labels.

    This is a bootstrap path when true click/book/judgment data does not exist yet.
    """

    prepared_catalog = prepare_catalog_for_v3(catalog=catalog)
    if prepared_catalog.empty:
        return _empty_training_dataset(label_strategy=LABEL_STRATEGY_WEAK)

    candidate_queries = list(queries) if queries is not None else generate_weak_supervision_queries(
        catalog=prepared_catalog,
        max_queries=max_queries,
        random_seed=random_seed,
    )
    if not candidate_queries:
        return _empty_training_dataset(label_strategy=LABEL_STRATEGY_WEAK)

    collected: list[pd.DataFrame] = []
    group_sizes: list[int] = []
    query_ids: list[str] = []
    query_contexts: dict[str, RankingFeatureContext] = {}

    for idx, request in enumerate(candidate_queries):
        artifacts = build_candidate_feature_artifacts(
            query=request,
            catalog=prepared_catalog,
            catalog_prepared=True,
        )
        features = artifacts.features.copy()
        if features.empty:
            continue

        features = features.head(max_candidates_per_query)
        if len(features) < min_candidates_per_query:
            continue

        labels = _derive_weak_labels(features)
        if labels.max() <= 0:
            labels[0] = 1

        query_id = f"weak-{idx:05d}"
        frame = features.copy()
        frame["query_id"] = query_id
        frame["label"] = labels.astype(np.int32)

        collected.append(frame)
        query_ids.append(query_id)
        group_sizes.append(len(frame))
        query_contexts[query_id] = artifacts.feature_context

    return _finalize_training_dataset(
        frames=collected,
        query_ids=query_ids,
        group_sizes=group_sizes,
        label_strategy=LABEL_STRATEGY_WEAK,
        query_contexts=query_contexts,
    )


def generate_weak_supervision_queries(
    *,
    catalog: pd.DataFrame,
    max_queries: int,
    random_seed: int,
) -> list[RecommendationQuery]:
    """Generate synthetic query contexts from catalog rows for weak supervision."""

    if catalog.empty or max_queries <= 0:
        return []

    sample_size = min(max_queries * 3, len(catalog))
    sampled = catalog.sample(n=sample_size, random_state=random_seed, replace=False)

    generated: list[RecommendationQuery] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for _, row in sampled.iterrows():
        query_text = _query_text_from_row(row)
        if not query_text:
            continue

        city = _clean_text(row.get("city", ""))
        country = _clean_text(row.get("country", ""))
        item_type = _item_type_from_entity_type(row.get("entity_type_norm", ""))

        dedupe_key = (query_text.lower(), item_type, city.lower(), country.lower())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        filters: dict[str, Any] = {
            "item_type": item_type,
            "is_open": True,
        }
        if city:
            filters["city"] = city
        if country:
            filters["country"] = country

        generated.append(
            RecommendationQuery(
                session_id=f"weak-train-{len(generated)}",
                query=query_text,
                constraints={},
                filters=filters,
                max_results=40,
                ranking_version="heuristic-v1",
            )
        )

        if len(generated) >= max_queries:
            break

    return generated


def build_feature_matrix(dataset: RankerTrainingDataset) -> pd.DataFrame:
    """Return numeric model matrix for the configured feature schema."""

    if dataset.frame.empty:
        return pd.DataFrame(columns=list(dataset.feature_columns))

    working = dataset.frame.copy()
    for column in dataset.feature_columns:
        if column not in working.columns:
            working[column] = 0.0

    matrix = (
        working[list(dataset.feature_columns)]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )
    return matrix


def split_train_validation_by_query(
    dataset: RankerTrainingDataset,
    *,
    validation_fraction: float = 0.2,
    random_seed: int = 13,
) -> DatasetSplit:
    """Split grouped ranking dataset by query_id to avoid leakage."""

    if dataset.frame.empty or not dataset.query_ids:
        empty = _empty_training_dataset(label_strategy=dataset.label_strategy)
        return DatasetSplit(train=empty, validation=empty)

    val_fraction = float(np.clip(validation_fraction, 0.05, 0.50))
    query_ids = np.array(list(dataset.query_ids), dtype=object)
    rng = np.random.default_rng(random_seed)
    shuffled = query_ids.copy()
    rng.shuffle(shuffled)

    val_count = max(1, int(round(len(shuffled) * val_fraction)))
    validation_ids = set(str(item) for item in shuffled[:val_count])

    validation_mask = dataset.frame["query_id"].astype(str).isin(validation_ids)
    validation_frame = dataset.frame[validation_mask].copy()
    train_frame = dataset.frame[~validation_mask].copy()

    if train_frame.empty:
        train_frame = validation_frame.iloc[0:0].copy()
    if validation_frame.empty:
        validation_frame = train_frame.iloc[0:0].copy()

    return DatasetSplit(
        train=_dataset_from_frame(
            train_frame,
            dataset.label_strategy,
            dataset.query_contexts,
        ),
        validation=_dataset_from_frame(
            validation_frame,
            dataset.label_strategy,
            dataset.query_contexts,
        ),
    )


def save_training_dataset(dataset: RankerTrainingDataset, path: Path) -> None:
    """Persist training frame for reproducibility."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".parquet":
        dataset.frame.to_parquet(path, index=False)
    else:
        dataset.frame.to_csv(path, index=False)


def load_judgments_csv(path: Path) -> pd.DataFrame:
    """Read explicit judgments from a CSV file."""

    return pd.read_csv(path, low_memory=False)


def _derive_weak_labels(features: pd.DataFrame) -> np.ndarray:
    numeric = features.copy()
    numeric = numeric.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    quality = (
        0.50 * np.clip(numeric["f_quality_stars"] / 5.0, 0.0, 1.0)
        + 0.30 * np.clip(numeric["f_quality_log_review_count"] / 6.5, 0.0, 1.0)
        + 0.20 * np.clip(numeric["f_quality_log_popularity"] / 4.0, 0.0, 1.0)
    )
    relevance = (
        0.50 * _saturating_positive(numeric["f_rel_text_overall"], scale=5.0)
        + 0.25 * np.clip(numeric["f_rel_query_token_coverage"], 0.0, 1.0)
        + 0.15 * np.clip(numeric["f_rel_query_phrase_in_name"], 0.0, 1.0)
        + 0.10 * np.clip(numeric["f_rel_query_phrase_in_description"], 0.0, 1.0)
    )
    alignment = (
        0.45 * np.clip(numeric["f_align_item_type_match"], 0.0, 1.0)
        + 0.35 * np.clip(numeric["f_align_entity_type_match"], 0.0, 1.0)
        + 0.20 * np.clip(numeric["f_align_category_term_coverage"], 0.0, 1.0)
    )
    geo = (
        0.42 * np.clip(numeric["f_geo_city_match"], 0.0, 1.0)
        + 0.18 * np.clip(numeric["f_geo_country_match"], 0.0, 1.0)
        + 0.12 * np.clip(numeric["f_geo_country_name_match"], 0.0, 1.0)
        + 0.10 * np.clip(numeric["f_geo_continent_match"], 0.0, 1.0)
        + 0.10 * _saturating_positive(numeric["f_geo_destination_match_count"], scale=2.0)
        + 0.08 * np.clip(numeric["f_geo_any_match"], 0.0, 1.0)
    )
    operational = (
        0.55 * np.clip(numeric["f_availability_open_requested_match"], 0.0, 1.0)
        + 0.30 * np.clip(numeric["f_price_best_effort_match"], 0.0, 1.0)
        + 0.15 * np.clip(numeric["f_metadata_completeness_score"], 0.0, 1.0)
    )

    weak_score = (
        0.34 * relevance
        + 0.26 * alignment
        + 0.16 * geo
        + 0.16 * quality
        + 0.08 * operational
    ).to_numpy(dtype=np.float32)

    if len(weak_score) == 0:
        return np.array([], dtype=np.int32)

    q_high = float(np.quantile(weak_score, 0.80))
    q_mid = float(np.quantile(weak_score, 0.55))
    q_low = float(np.quantile(weak_score, 0.30))

    labels = np.zeros(len(weak_score), dtype=np.int32)
    labels[weak_score >= q_low] = 1
    labels[weak_score >= q_mid] = 2
    labels[weak_score >= q_high] = 3

    top_idx = int(np.argmax(weak_score))
    labels[top_idx] = max(labels[top_idx], 2)
    return labels


def _saturating_positive(series: pd.Series, *, scale: float) -> pd.Series:
    safe = np.maximum(series.astype(np.float32), 0.0)
    if scale <= 0:
        return safe.clip(lower=0.0, upper=1.0)
    return (1.0 - np.exp(-safe / scale)).astype(np.float32)


def _query_from_judgment_group(
    *,
    query_id: str,
    group: pd.DataFrame,
) -> RecommendationQuery:
    first = group.iloc[0]
    raw_filters = first.get("filters_json", first.get("filters", {}))
    raw_constraints = first.get("constraints_json", first.get("constraints", {}))

    filters = _coerce_json_object(raw_filters)
    constraints = _coerce_json_object(raw_constraints)

    session_id = _clean_text(first.get("session_id", "")) or f"judgment-{query_id}"
    query_text = _clean_text(first.get("query", "")) or "recommendations"
    max_results = _coerce_int(first.get("max_results", 40), default=40, minimum=1, maximum=50)

    return RecommendationQuery(
        session_id=session_id,
        query=query_text,
        constraints=constraints,
        filters=filters,
        max_results=max_results,
        ranking_version="heuristic-v1",
    )


def _query_text_from_row(row: pd.Series) -> str:
    category = _primary_category_term(_clean_text(row.get("categories_norm", "")))
    entity_type = _clean_text(row.get("entity_type_norm", ""))
    city = _clean_text(row.get("city", ""))
    country_name = _clean_text(row.get("country_name", ""))
    name = _clean_text(row.get("name", ""))

    topic = category or entity_type or "places"
    noun = entity_type or "places"

    if city:
        return f"{topic} {noun} in {city}".strip()
    if country_name:
        return f"{topic} {noun} in {country_name}".strip()
    if name:
        return f"{topic} like {name}".strip()
    return ""


def _primary_category_term(categories_norm: str) -> str:
    if not categories_norm:
        return ""

    tokens = [token.strip() for token in categories_norm.split() if token.strip()]
    for token in tokens:
        if token in _IGNORED_CATEGORY_TERMS:
            continue
        if len(token) <= 2:
            continue
        return token
    return ""


def _item_type_from_entity_type(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if normalized in _ITEM_TYPE_BY_ENTITY_TYPE:
        return _ITEM_TYPE_BY_ENTITY_TYPE[normalized]
    return "destination"


def _coerce_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, coerced))


def _dataset_from_frame(
    frame: pd.DataFrame,
    label_strategy: str,
    context_lookup: dict[str, RankingFeatureContext],
) -> RankerTrainingDataset:
    if frame.empty:
        return _empty_training_dataset(label_strategy=label_strategy)

    ordered = frame.copy()
    ordered["query_id"] = ordered["query_id"].astype(str)
    ordered["business_id"] = ordered["business_id"].astype(str)
    ordered["label"] = pd.to_numeric(ordered["label"], errors="coerce").fillna(0).astype(np.int32)

    query_sizes = ordered.groupby("query_id", sort=True).size()
    query_ids = tuple(query_sizes.index.astype(str).tolist())
    return RankerTrainingDataset(
        frame=ordered,
        feature_columns=ML_FEATURE_COLUMNS,
        query_ids=query_ids,
        group_sizes=tuple(int(value) for value in query_sizes.tolist()),
        label_strategy=label_strategy,
        query_contexts={
            query_id: context_lookup[query_id]
            for query_id in query_ids
            if query_id in context_lookup
        },
    )


def _finalize_training_dataset(
    *,
    frames: list[pd.DataFrame],
    query_ids: list[str],
    group_sizes: list[int],
    label_strategy: str,
    query_contexts: dict[str, RankingFeatureContext],
) -> RankerTrainingDataset:
    if not frames:
        return _empty_training_dataset(label_strategy=label_strategy)

    combined = pd.concat(frames, ignore_index=True)
    for column in ML_FEATURE_COLUMNS:
        if column not in combined.columns:
            combined[column] = 0.0

    combined[list(ML_FEATURE_COLUMNS)] = (
        combined[list(ML_FEATURE_COLUMNS)]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )
    combined["label"] = pd.to_numeric(combined["label"], errors="coerce").fillna(0).astype(np.int32)

    ordered_columns = ["query_id", "business_id", "label", *ML_FEATURE_COLUMNS]
    combined = combined[ordered_columns]

    return RankerTrainingDataset(
        frame=combined,
        feature_columns=ML_FEATURE_COLUMNS,
        query_ids=tuple(query_ids),
        group_sizes=tuple(group_sizes),
        label_strategy=label_strategy,
        query_contexts=dict(query_contexts),
    )


def _empty_training_dataset(*, label_strategy: str) -> RankerTrainingDataset:
    columns = ["query_id", "business_id", "label", *ML_FEATURE_COLUMNS]
    return RankerTrainingDataset(
        frame=pd.DataFrame(columns=columns),
        feature_columns=ML_FEATURE_COLUMNS,
        query_ids=tuple(),
        group_sizes=tuple(),
        label_strategy=label_strategy,
        query_contexts={},
    )


__all__ = [
    "DatasetSplit",
    "LABEL_STRATEGY_EXPLICIT",
    "LABEL_STRATEGY_WEAK",
    "RankerTrainingDataset",
    "build_feature_matrix",
    "build_training_dataset_from_judgments",
    "build_weak_supervision_training_dataset",
    "generate_weak_supervision_queries",
    "load_judgments_csv",
    "save_training_dataset",
    "split_train_validation_by_query",
]
