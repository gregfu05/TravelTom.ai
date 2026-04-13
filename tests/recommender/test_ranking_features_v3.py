"""Tests for ranking feature engineering in recommender_v3 Step 2."""

from __future__ import annotations

import numpy as np
import pandas as pd

from traveltom.recommendor.ranking_features_v3 import (
    RANKING_FEATURE_COLUMNS,
    RankingFeatureContext,
    build_ranking_features,
)


def _context(**overrides) -> RankingFeatureContext:
    base = RankingFeatureContext(
        normalized_query_text="seafood hotel santa barbara",
        query_tokens=("seafood", "hotel", "santa", "barbara"),
        category_terms=("seafood", "hotel"),
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


def _candidates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "business_id": "h1",
                "name": "Sunset Hotel",
                "name_norm": "sunset hotel",
                "entity_type": "hotel",
                "entity_type_norm": "hotel",
                "city": "Santa Barbara",
                "city_norm": "santa barbara",
                "state": "CA",
                "state_norm": "ca",
                "country": "US",
                "country_norm": "us",
                "country_name": "United States",
                "country_name_norm": "united states",
                "continent": "North America",
                "continent_norm": "north america",
                "categories": "hotel;seafood",
                "categories_norm": "hotel seafood",
                "description": "Seafood near the beach",
                "description_norm": "seafood near the beach",
                "website": "https://hotel.example",
                "phone": "+1-111-111",
                "address": "123 Harbor St",
                "source": "seed",
                "stars": 4.5,
                "review_count": 100,
                "popularity": 8.0,
                "is_open": 1,
                "price_level": 3.0,
                "latitude": 34.4,
                "longitude": -119.7,
                "retrieval_score": 10.0,
                "retrieval_text_match": 4.0,
                "retrieval_category_match": 3.0,
                "retrieval_geo_match": 2.0,
                "retrieval_entity_type_match": 1.0,
                "retrieval_price_match": 1.0,
            },
            {
                "business_id": "r1",
                "name": "Bistro",
                "name_norm": "bistro",
                "entity_type": "restaurant",
                "entity_type_norm": "restaurant",
                "city": "Paris",
                "city_norm": "paris",
                "state": "",
                "state_norm": "",
                "country": "FR",
                "country_norm": "fr",
                "country_name": "France",
                "country_name_norm": "france",
                "continent": "Europe",
                "continent_norm": "europe",
                "categories": "restaurant;french",
                "categories_norm": "restaurant french",
                "description": "",
                "description_norm": "",
                "website": "",
                "phone": "",
                "address": "",
                "source": "",
                "stars": 4.0,
                "review_count": 20,
                "popularity": 2.0,
                "is_open": 1,
                "price_level": np.nan,
                "latitude": np.nan,
                "longitude": np.nan,
                "retrieval_score": 1.0,
                "retrieval_text_match": 0.0,
                "retrieval_category_match": 0.0,
                "retrieval_geo_match": 0.0,
                "retrieval_entity_type_match": 0.0,
                "retrieval_price_match": 0.0,
            },
        ]
    )


def test_feature_frame_has_required_columns_and_rows() -> None:
    artifacts = build_ranking_features(context=_context(), candidates=_candidates())
    frame = artifacts.features

    assert list(frame.columns) == list(RANKING_FEATURE_COLUMNS)
    assert frame["business_id"].tolist() == ["h1", "r1"]


def test_missing_values_are_safe_and_numeric() -> None:
    artifacts = build_ranking_features(context=_context(), candidates=_candidates())
    frame = artifacts.features

    numeric = frame.drop(columns=["business_id"])
    assert not numeric.isna().any().any()
    assert frame.loc[1, "f_metadata_has_description"] == 0.0
    assert frame.loc[1, "f_metadata_has_coordinates"] == 0.0
    assert frame.loc[1, "f_price_level_known"] == 0.0


def test_entity_geo_and_item_type_alignment_features() -> None:
    artifacts = build_ranking_features(context=_context(), candidates=_candidates())
    frame = artifacts.features.set_index("business_id")

    assert frame.loc["h1", "f_align_entity_type_match"] == 1.0
    assert frame.loc["r1", "f_align_entity_type_match"] == 0.0
    assert frame.loc["h1", "f_align_item_type_match"] == 1.0
    assert frame.loc["r1", "f_align_item_type_match"] == 0.0
    assert frame.loc["h1", "f_geo_city_match"] == 1.0
    assert frame.loc["r1", "f_geo_city_match"] == 0.0
    assert (
        frame.loc["h1", "f_geo_destination_match_count"]
        > frame.loc["r1", "f_geo_destination_match_count"]
    )


def test_text_alignment_features_rank_more_relevant_candidate_higher() -> None:
    artifacts = build_ranking_features(context=_context(), candidates=_candidates())
    frame = artifacts.features.set_index("business_id")

    assert (
        frame.loc["h1", "f_rel_name_token_hits"]
        > frame.loc["r1", "f_rel_name_token_hits"]
    )
    assert frame.loc["h1", "f_rel_text_overall"] > frame.loc["r1", "f_rel_text_overall"]
    assert (
        frame.loc["h1", "f_align_category_term_hits"]
        > frame.loc["r1", "f_align_category_term_hits"]
    )
