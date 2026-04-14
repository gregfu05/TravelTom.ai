"""Tests for Step 4 training data pipeline."""

from __future__ import annotations

import pandas as pd
from app.schemas.tools.recommendations import RecommendationQuery

from traveltom.recommendor.ml_ranker_v3 import ML_FEATURE_COLUMNS
from traveltom.recommendor.ml_training_v3 import (
    LABEL_STRATEGY_EXPLICIT,
    LABEL_STRATEGY_WEAK,
    build_feature_matrix,
    build_training_dataset_from_judgments,
    build_weak_supervision_training_dataset,
    split_train_validation_by_query,
)


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "business_id": "r-sb-1",
                "name": "La Mesa Seafood",
                "city": "Santa Barbara",
                "state": "CA",
                "country": "US",
                "country_name": "United States",
                "continent": "North America",
                "latitude": 34.41,
                "longitude": -119.69,
                "stars": 4.8,
                "review_count": 210,
                "categories": "restaurant;seafood;bar",
                "attributes": None,
                "is_open": 1,
                "address": "B St",
                "price_level": 2.0,
                "description": "Fresh seafood and late dinner service.",
                "website": "",
                "phone": "",
                "source": "seed",
                "entity_type": "restaurant",
                "popularity": 8.5,
            },
            {
                "business_id": "h-sb-1",
                "name": "Sunset Inn",
                "city": "Santa Barbara",
                "state": "CA",
                "country": "US",
                "country_name": "United States",
                "continent": "North America",
                "latitude": 34.40,
                "longitude": -119.70,
                "stars": 4.6,
                "review_count": 120,
                "categories": "hotel;beachfront;family",
                "attributes": None,
                "is_open": 1,
                "address": "A St",
                "price_level": 3.0,
                "description": "A beach hotel with family suites.",
                "website": "https://example.com/sunset",
                "phone": "",
                "source": "seed",
                "entity_type": "hotel",
                "popularity": 9.0,
            },
            {
                "business_id": "a-sb-1",
                "name": "Botanical Garden",
                "city": "Santa Barbara",
                "state": "CA",
                "country": "US",
                "country_name": "United States",
                "continent": "North America",
                "latitude": 34.42,
                "longitude": -119.72,
                "stars": 4.5,
                "review_count": 150,
                "categories": "attraction;garden;nature",
                "attributes": None,
                "is_open": 1,
                "address": "C St",
                "price_level": None,
                "description": "Outdoor garden attraction.",
                "website": "",
                "phone": "",
                "source": "seed",
                "entity_type": "attraction",
                "popularity": 8.0,
            },
            {
                "business_id": "r-par-1",
                "name": "Le Bistro",
                "city": "Paris",
                "state": "Ile-de-France",
                "country": "FR",
                "country_name": "France",
                "continent": "Europe",
                "latitude": 48.86,
                "longitude": 2.35,
                "stars": 4.9,
                "review_count": 300,
                "categories": "restaurant;french",
                "attributes": None,
                "is_open": 1,
                "address": "D St",
                "price_level": 4.0,
                "description": "French tasting menu.",
                "website": "",
                "phone": "",
                "source": "seed",
                "entity_type": "restaurant",
                "popularity": 9.5,
            },
        ]
    )


def _queries() -> list[RecommendationQuery]:
    return [
        RecommendationQuery(
            session_id="s1",
            query="seafood in santa barbara",
            constraints={},
            filters={"item_type": "restaurant", "city": "Santa Barbara"},
            max_results=20,
            ranking_version="heuristic-v1",
        ),
        RecommendationQuery(
            session_id="s2",
            query="hotels in santa barbara",
            constraints={},
            filters={"item_type": "hotel", "city": "Santa Barbara"},
            max_results=20,
            ranking_version="heuristic-v1",
        ),
    ]


def test_build_weak_supervision_training_dataset() -> None:
    dataset = build_weak_supervision_training_dataset(
        catalog=_catalog(),
        queries=_queries(),
        max_queries=5,
        random_seed=7,
        max_candidates_per_query=40,
        min_candidates_per_query=1,
    )

    assert dataset.label_strategy == LABEL_STRATEGY_WEAK
    assert not dataset.frame.empty
    assert set(["query_id", "business_id", "label"]).issubset(dataset.frame.columns)
    assert sum(dataset.group_sizes) == len(dataset.frame)
    assert all(query_id in dataset.query_contexts for query_id in dataset.query_ids)
    assert (dataset.frame["label"] >= 0).all()


def test_build_training_dataset_from_explicit_judgments() -> None:
    judgments = pd.DataFrame(
        [
            {
                "query_id": "q1",
                "session_id": "j1",
                "query": "seafood in santa barbara",
                "filters_json": '{"item_type":"restaurant", "city":"Santa Barbara"}',
                "constraints_json": "{}",
                "business_id": "r-sb-1",
                "label": 3,
            },
            {
                "query_id": "q1",
                "session_id": "j1",
                "query": "seafood in santa barbara",
                "filters_json": '{"item_type":"restaurant", "city":"Santa Barbara"}',
                "constraints_json": "{}",
                "business_id": "a-sb-1",
                "label": 1,
            },
            {
                "query_id": "q2",
                "session_id": "j2",
                "query": "hotel in santa barbara",
                "filters_json": '{"item_type":"hotel", "city":"Santa Barbara"}',
                "constraints_json": "{}",
                "business_id": "h-sb-1",
                "label": 3,
            },
        ]
    )

    dataset = build_training_dataset_from_judgments(
        judgments=judgments,
        catalog=_catalog(),
        max_candidates_per_query=40,
        min_candidates_per_query=1,
    )

    assert dataset.label_strategy == LABEL_STRATEGY_EXPLICIT
    assert not dataset.frame.empty
    assert set(dataset.query_ids) == {"q1", "q2"}
    assert dataset.frame["label"].max() >= 3


def test_feature_matrix_uses_stable_columns() -> None:
    dataset = build_weak_supervision_training_dataset(
        catalog=_catalog(),
        queries=_queries(),
        max_candidates_per_query=40,
        min_candidates_per_query=1,
    )

    matrix = build_feature_matrix(dataset)
    assert list(matrix.columns) == list(ML_FEATURE_COLUMNS)
    assert not matrix.isna().any().any()


def test_split_train_validation_by_query_preserves_grouping() -> None:
    dataset = build_weak_supervision_training_dataset(
        catalog=_catalog(),
        queries=_queries(),
        max_candidates_per_query=40,
        min_candidates_per_query=1,
    )

    split = split_train_validation_by_query(
        dataset,
        validation_fraction=0.5,
        random_seed=42,
    )

    assert sum(split.train.group_sizes) == len(split.train.frame)
    assert sum(split.validation.group_sizes) == len(split.validation.frame)
    assert set(split.train.query_ids).isdisjoint(set(split.validation.query_ids))
