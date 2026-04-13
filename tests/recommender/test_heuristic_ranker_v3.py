"""Tests for Step 3 heuristic ranker behavior."""

from __future__ import annotations

import numpy as np
import pandas as pd

from traveltom.recommendor.heuristic_ranker_v3 import (
    HeuristicRankerConfig,
    HeuristicRankerV3,
)
from traveltom.recommendor.ranking_features_v3 import RankingFeatureContext


def _context(**overrides) -> RankingFeatureContext:
    base = RankingFeatureContext(
        normalized_query_text="beach hotel santa barbara",
        query_tokens=("beach", "hotel", "santa", "barbara"),
        category_terms=("beach", "hotel"),
        entity_types=("hotel",),
        requested_item_type="hotel",
        city="santa barbara",
        state=None,
        country="us",
        country_name="united states",
        continent="north america",
        destination_hint="santa barbara",
        require_open=True,
        price_level_min=2.0,
        price_level_max=4.0,
    )
    return RankingFeatureContext(**{**base.__dict__, **overrides})


def _feature_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "business_id": "relevant_a",
                "f_quality_stars": 4.4,
                "f_quality_log_review_count": 3.0,
                "f_quality_log_popularity": 1.8,
                "f_rel_name_token_hits": 2.0,
                "f_rel_category_token_hits": 2.0,
                "f_rel_description_token_hits": 1.0,
                "f_rel_query_phrase_in_name": 0.0,
                "f_rel_query_phrase_in_description": 0.0,
                "f_rel_query_token_coverage": 1.0,
                "f_rel_text_overall": 6.0,
                "f_align_category_term_coverage": 1.0,
                "f_align_entity_type_constraint_present": 1.0,
                "f_align_entity_type_match": 1.0,
                "f_align_item_type_constraint_present": 1.0,
                "f_align_item_type_match": 1.0,
                "f_geo_city_match": 1.0,
                "f_geo_state_match": 0.0,
                "f_geo_country_match": 1.0,
                "f_geo_country_name_match": 1.0,
                "f_geo_continent_match": 1.0,
                "f_geo_destination_match_count": 2.0,
                "f_geo_any_match": 1.0,
                "f_availability_open_requested_match": 1.0,
                "f_price_best_effort_match": 1.0,
                "f_price_level_known": 1.0,
                "f_metadata_completeness_score": 0.9,
                "f_struct_description_token_count": 20.0,
                "f_struct_category_count": 3.0,
                "f_struct_missing_primary_text": 0.0,
            },
            {
                "business_id": "popular_but_generic",
                "f_quality_stars": 5.0,
                "f_quality_log_review_count": 7.5,
                "f_quality_log_popularity": 3.8,
                "f_rel_name_token_hits": 0.0,
                "f_rel_category_token_hits": 0.0,
                "f_rel_description_token_hits": 0.0,
                "f_rel_query_phrase_in_name": 0.0,
                "f_rel_query_phrase_in_description": 0.0,
                "f_rel_query_token_coverage": 0.0,
                "f_rel_text_overall": 0.0,
                "f_align_category_term_coverage": 0.0,
                "f_align_entity_type_constraint_present": 1.0,
                "f_align_entity_type_match": 0.0,
                "f_align_item_type_constraint_present": 1.0,
                "f_align_item_type_match": 0.0,
                "f_geo_city_match": 0.0,
                "f_geo_state_match": 0.0,
                "f_geo_country_match": 0.0,
                "f_geo_country_name_match": 0.0,
                "f_geo_continent_match": 0.0,
                "f_geo_destination_match_count": 0.0,
                "f_geo_any_match": 0.0,
                "f_availability_open_requested_match": 1.0,
                "f_price_best_effort_match": 1.0,
                "f_price_level_known": 1.0,
                "f_metadata_completeness_score": 0.6,
                "f_struct_description_token_count": 8.0,
                "f_struct_category_count": 2.0,
                "f_struct_missing_primary_text": 0.0,
            },
            {
                "business_id": "geo_match_low_pop",
                "f_quality_stars": 4.0,
                "f_quality_log_review_count": 2.4,
                "f_quality_log_popularity": 1.2,
                "f_rel_name_token_hits": 1.0,
                "f_rel_category_token_hits": 1.0,
                "f_rel_description_token_hits": 0.5,
                "f_rel_query_phrase_in_name": 0.0,
                "f_rel_query_phrase_in_description": 0.0,
                "f_rel_query_token_coverage": 0.5,
                "f_rel_text_overall": 3.0,
                "f_align_category_term_coverage": 0.5,
                "f_align_entity_type_constraint_present": 1.0,
                "f_align_entity_type_match": 1.0,
                "f_align_item_type_constraint_present": 1.0,
                "f_align_item_type_match": 1.0,
                "f_geo_city_match": 1.0,
                "f_geo_state_match": 0.0,
                "f_geo_country_match": 1.0,
                "f_geo_country_name_match": 1.0,
                "f_geo_continent_match": 1.0,
                "f_geo_destination_match_count": 2.0,
                "f_geo_any_match": 1.0,
                "f_availability_open_requested_match": 1.0,
                "f_price_best_effort_match": 0.6,
                "f_price_level_known": 0.0,
                "f_metadata_completeness_score": 0.5,
                "f_struct_description_token_count": 4.0,
                "f_struct_category_count": 2.0,
                "f_struct_missing_primary_text": 0.0,
            },
        ]
    )


def test_ranker_has_explicit_version_and_config() -> None:
    config = HeuristicRankerConfig()
    ranker = HeuristicRankerV3(config)
    assert ranker.version == "heuristic-ranker-v3"


def test_ranker_returns_component_scores_and_final_score() -> None:
    ranker = HeuristicRankerV3()
    result = ranker.score(features=_feature_frame(), context=_context())

    assert result.version == "heuristic-ranker-v3"
    expected_columns = {
        "score_quality",
        "score_relevance",
        "score_alignment",
        "score_geo",
        "score_operational",
        "score_completeness",
        "score_final",
    }
    assert expected_columns.issubset(set(result.scored.columns))


def test_relevance_and_alignment_beat_generic_popularity() -> None:
    ranker = HeuristicRankerV3()
    scored = ranker.score(features=_feature_frame(), context=_context()).scored
    ordered_ids = scored["business_id"].tolist()

    assert ordered_ids.index("relevant_a") < ordered_ids.index("popular_but_generic")


def test_geo_intent_can_outweigh_raw_popularity_when_needed() -> None:
    ranker = HeuristicRankerV3()
    scored = ranker.score(features=_feature_frame(), context=_context()).scored
    ordered_ids = scored["business_id"].tolist()

    assert ordered_ids.index("geo_match_low_pop") < ordered_ids.index(
        "popular_but_generic"
    )


def test_missing_values_do_not_break_scoring() -> None:
    frame = _feature_frame()
    frame.loc[1, "f_quality_log_review_count"] = np.nan
    frame.loc[1, "f_rel_text_overall"] = np.nan

    ranker = HeuristicRankerV3()
    scored = ranker.score(features=frame, context=_context()).scored

    numeric = scored.drop(columns=["business_id"])
    assert not numeric.isna().any().any()
    assert (scored["score_final"] >= 0).all()
