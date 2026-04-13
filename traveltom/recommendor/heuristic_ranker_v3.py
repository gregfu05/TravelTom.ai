"""Step 3 heuristic baseline ranker for recommender_v3.

Interface is ranker-agnostic: feature frame in, scored frame out.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from traveltom.recommendor.ranking_features_v3 import RankingFeatureContext

_REQUIRED_FEATURE_COLUMNS = (
    "f_quality_stars",
    "f_quality_review_count",
    "f_quality_log_review_count",
    "f_quality_log_popularity",
    "f_rel_name_token_hits",
    "f_rel_category_token_hits",
    "f_rel_description_token_hits",
    "f_rel_query_phrase_in_name",
    "f_rel_query_phrase_in_description",
    "f_rel_query_token_coverage",
    "f_rel_text_overall",
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
    "f_availability_open_requested_match",
    "f_price_best_effort_match",
    "f_price_level_known",
    "f_metadata_completeness_score",
    "f_struct_description_token_count",
    "f_struct_category_count",
    "f_struct_missing_primary_text",
)


@dataclass(frozen=True)
class HeuristicRankerConfig:
    """Configurable weights and transforms for heuristic ranking."""

    version: str = "heuristic-ranker-v3"

    weight_relevance: float = 0.30
    weight_alignment: float = 0.20
    weight_geo_with_constraints: float = 0.20
    weight_geo_without_constraints: float = 0.08
    weight_quality: float = 0.18
    weight_operational: float = 0.08
    weight_completeness: float = 0.04

    quality_review_log_scale: float = 6.5
    quality_popularity_log_scale: float = 4.0

    relevance_name_scale: float = 2.0
    relevance_category_scale: float = 2.0
    relevance_description_scale: float = 2.5
    relevance_overall_scale: float = 5.0

    geo_destination_scale: float = 2.0
    completeness_description_token_scale: float = 24.0
    completeness_category_count_scale: float = 4.0


@dataclass(frozen=True)
class HeuristicRankerOutput:
    """Ranker output for integration and debugging."""

    scored: pd.DataFrame
    version: str


class HeuristicRankerV3:
    """Versioned, interpretable heuristic scorer over engineered features."""

    def __init__(self, config: HeuristicRankerConfig | None = None) -> None:
        self._config = config or HeuristicRankerConfig()

    @property
    def version(self) -> str:
        return self._config.version

    def score(
        self,
        *,
        features: pd.DataFrame,
        context: RankingFeatureContext,
    ) -> HeuristicRankerOutput:
        if features.empty:
            return HeuristicRankerOutput(scored=features.copy(), version=self.version)

        scored = features.copy()
        scored = _ensure_numeric_features(scored)

        quality = _compute_quality_component(scored, self._config)
        relevance = _compute_relevance_component(scored, self._config)
        alignment = _compute_alignment_component(scored)
        geo = _compute_geo_component(scored, self._config)
        operational = _compute_operational_component(scored)
        completeness = _compute_completeness_component(scored, self._config)

        geo_weight = (
            self._config.weight_geo_with_constraints
            if _has_geo_constraints(context)
            else self._config.weight_geo_without_constraints
        )
        relevance_weight = (
            self._config.weight_relevance
            + (self._config.weight_geo_with_constraints - geo_weight) * 0.60
        )
        quality_weight = (
            self._config.weight_quality
            + (self._config.weight_geo_with_constraints - geo_weight) * 0.40
        )

        scored["score_quality"] = quality
        scored["score_relevance"] = relevance
        scored["score_alignment"] = alignment
        scored["score_geo"] = geo
        scored["score_operational"] = operational
        scored["score_completeness"] = completeness

        scored["score_final"] = (
            quality_weight * scored["score_quality"]
            + relevance_weight * scored["score_relevance"]
            + self._config.weight_alignment * scored["score_alignment"]
            + geo_weight * scored["score_geo"]
            + self._config.weight_operational * scored["score_operational"]
            + self._config.weight_completeness * scored["score_completeness"]
        )

        scored = scored.sort_values(
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

        return HeuristicRankerOutput(scored=scored, version=self.version)


def _compute_quality_component(
    features: pd.DataFrame,
    config: HeuristicRankerConfig,
) -> pd.Series:
    stars = _clip01(features["f_quality_stars"] / 5.0)
    reviews = _clip01(features["f_quality_log_review_count"] / config.quality_review_log_scale)
    popularity = _clip01(
        features["f_quality_log_popularity"] / config.quality_popularity_log_scale
    )

    return (0.50 * stars + 0.30 * reviews + 0.20 * popularity).astype(np.float32)


def _compute_relevance_component(
    features: pd.DataFrame,
    config: HeuristicRankerConfig,
) -> pd.Series:
    name_match = _saturating_positive(
        features["f_rel_name_token_hits"],
        scale=config.relevance_name_scale,
    )
    category_match = _saturating_positive(
        features["f_rel_category_token_hits"],
        scale=config.relevance_category_scale,
    )
    description_match = _saturating_positive(
        features["f_rel_description_token_hits"],
        scale=config.relevance_description_scale,
    )
    overall_match = _saturating_positive(
        features["f_rel_text_overall"],
        scale=config.relevance_overall_scale,
    )

    token_coverage = _clip01(features["f_rel_query_token_coverage"])
    phrase_match = np.maximum(
        features["f_rel_query_phrase_in_name"],
        features["f_rel_query_phrase_in_description"],
    )

    return (
        0.40 * overall_match
        + 0.20 * token_coverage
        + 0.15 * name_match
        + 0.12 * category_match
        + 0.08 * description_match
        + 0.05 * phrase_match
    ).astype(np.float32)


def _compute_alignment_component(features: pd.DataFrame) -> pd.Series:
    item_constraint = features["f_align_item_type_constraint_present"]
    entity_constraint = features["f_align_entity_type_constraint_present"]

    item_match = np.where(
        item_constraint > 0,
        features["f_align_item_type_match"],
        0.5,
    )
    entity_match = np.where(
        entity_constraint > 0,
        features["f_align_entity_type_match"],
        0.5,
    )

    category_alignment = _clip01(features["f_align_category_term_coverage"])

    return (
        0.45 * item_match + 0.35 * entity_match + 0.20 * category_alignment
    ).astype(np.float32)


def _compute_geo_component(
    features: pd.DataFrame,
    config: HeuristicRankerConfig,
) -> pd.Series:
    destination_match = _saturating_positive(
        features["f_geo_destination_match_count"],
        scale=config.geo_destination_scale,
    )

    return (
        0.35 * features["f_geo_city_match"]
        + 0.12 * features["f_geo_state_match"]
        + 0.16 * features["f_geo_country_match"]
        + 0.10 * features["f_geo_country_name_match"]
        + 0.09 * features["f_geo_continent_match"]
        + 0.12 * destination_match
        + 0.06 * features["f_geo_any_match"]
    ).astype(np.float32)


def _compute_operational_component(features: pd.DataFrame) -> pd.Series:
    price_fit = features["f_price_best_effort_match"]
    price_known = features["f_price_level_known"]

    return (
        0.55 * features["f_availability_open_requested_match"]
        + 0.30 * price_fit
        + 0.15 * price_known
    ).astype(np.float32)


def _compute_completeness_component(
    features: pd.DataFrame,
    config: HeuristicRankerConfig,
) -> pd.Series:
    description_richness = _saturating_positive(
        features["f_struct_description_token_count"],
        scale=config.completeness_description_token_scale,
    )
    category_richness = _saturating_positive(
        features["f_struct_category_count"],
        scale=config.completeness_category_count_scale,
    )

    return (
        0.55 * features["f_metadata_completeness_score"]
        + 0.20 * description_richness
        + 0.15 * category_richness
        + 0.10 * (1.0 - features["f_struct_missing_primary_text"])
    ).astype(np.float32)


def _has_geo_constraints(context: RankingFeatureContext) -> bool:
    return any(
        value is not None
        for value in (
            context.city,
            context.state,
            context.country,
            context.country_name,
            context.continent,
            context.destination_hint,
        )
    )


def _saturating_positive(series: pd.Series, *, scale: float) -> pd.Series:
    safe = np.maximum(series.astype(np.float32), 0.0)
    if scale <= 0:
        return _clip01(safe)
    return (1.0 - np.exp(-safe / scale)).astype(np.float32)


def _clip01(series: pd.Series) -> pd.Series:
    return series.clip(lower=0.0, upper=1.0).astype(np.float32)


def _ensure_numeric_features(features: pd.DataFrame) -> pd.DataFrame:
    working = features.copy()
    if "business_id" not in working.columns:
        working["business_id"] = ""

    for column in _REQUIRED_FEATURE_COLUMNS:
        if column not in working.columns:
            working[column] = 0.0

    numeric_cols = [column for column in working.columns if column != "business_id"]
    working[numeric_cols] = working[numeric_cols].apply(
        pd.to_numeric,
        errors="coerce",
    ).fillna(0.0)

    return working


__all__ = [
    "HeuristicRankerConfig",
    "HeuristicRankerOutput",
    "HeuristicRankerV3",
]
