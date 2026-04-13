"""Tests for Step 4 ML ranker path."""

from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
from traveltom.recommendor.ml_ranker_v3 import (
    ML_FEATURE_COLUMNS,
    LightGBMLTRRankerV3,
    MLRankerConfig,
    clear_ml_ranker_cache,
    load_artifact_metadata,
)
from traveltom.recommendor.ranking_features_v3 import RankingFeatureContext


class DummyPredictModel:
    def predict(self, matrix: pd.DataFrame) -> np.ndarray:
        return matrix["f_rel_text_overall"].to_numpy(dtype=np.float32) + 0.2 * matrix[
            "f_quality_stars"
        ].to_numpy(dtype=np.float32)


class BrokenPredictModel:
    def predict(self, matrix: pd.DataFrame) -> np.ndarray:
        raise RuntimeError("predict failed")


def _context() -> RankingFeatureContext:
    return RankingFeatureContext(
        normalized_query_text="seafood santa barbara",
        query_tokens=("seafood", "santa", "barbara"),
        category_terms=("seafood",),
        entity_types=("restaurant",),
        requested_item_type="destination",
        city="santa barbara",
        state=None,
        country="us",
        country_name="united states",
        continent="north america",
        destination_hint="santa barbara",
        require_open=True,
        price_level_min=None,
        price_level_max=None,
    )


def _feature_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "business_id": "a",
                "f_quality_stars": 4.6,
                "f_quality_review_count": 100,
                "f_rel_text_overall": 4.0,
            },
            {
                "business_id": "b",
                "f_quality_stars": 4.9,
                "f_quality_review_count": 400,
                "f_rel_text_overall": 1.0,
            },
        ]
    )


def test_ml_feature_columns_are_stable() -> None:
    assert "business_id" not in ML_FEATURE_COLUMNS
    assert "f_quality_stars" in ML_FEATURE_COLUMNS
    assert "f_rel_text_overall" in ML_FEATURE_COLUMNS


def test_ml_ranker_falls_back_when_artifact_missing(tmp_path) -> None:
    missing = tmp_path / "missing.pkl"
    ranker = LightGBMLTRRankerV3(config=MLRankerConfig(artifact_path=missing))

    output = ranker.score(features=_feature_frame(), context=_context())

    assert output.used_fallback is True
    assert output.fallback_reason == "artifact_unavailable"
    assert "fallback-heuristic-ranker-v3" in output.version
    assert "score_ml" in output.scored.columns


def test_ml_ranker_loads_artifact_and_scores(tmp_path) -> None:
    artifact_path = tmp_path / "ranker.pkl"
    payload = {
        "model": DummyPredictModel(),
        "feature_columns": [
            "f_rel_text_overall",
            "f_quality_stars",
            "f_quality_review_count",
        ],
        "model_version": "test-v1",
        "model_family": "lightgbm-ltr",
        "schema_version": "ranking-features-v3-v1",
        "label_strategy": "weak-supervision-v1",
    }
    with artifact_path.open("wb") as handle:
        pickle.dump(payload, handle)

    ranker = LightGBMLTRRankerV3(config=MLRankerConfig(artifact_path=artifact_path))
    output = ranker.score(features=_feature_frame(), context=_context())

    assert output.used_fallback is False
    assert output.version.endswith("@test-v1")
    assert "score_ml" in output.scored.columns
    assert output.scored.iloc[0]["business_id"] == "a"


def test_ml_ranker_falls_back_on_prediction_failure(tmp_path) -> None:
    artifact_path = tmp_path / "broken.pkl"
    payload = {
        "model": BrokenPredictModel(),
        "feature_columns": ["f_rel_text_overall", "f_quality_stars"],
        "model_version": "broken",
        "model_family": "lightgbm-ltr",
        "schema_version": "ranking-features-v3-v1",
        "label_strategy": "weak-supervision-v1",
    }
    with artifact_path.open("wb") as handle:
        pickle.dump(payload, handle)

    ranker = LightGBMLTRRankerV3(config=MLRankerConfig(artifact_path=artifact_path))
    output = ranker.score(features=_feature_frame(), context=_context())

    assert output.used_fallback is True
    assert output.fallback_reason is not None
    assert output.fallback_reason.startswith("prediction_failure:")


def test_load_artifact_metadata(tmp_path) -> None:
    artifact_path = tmp_path / "meta.pkl"
    payload = {
        "model": DummyPredictModel(),
        "feature_columns": ["f_rel_text_overall"],
        "model_version": "m1",
        "model_family": "lightgbm-ltr",
        "schema_version": "ranking-features-v3-v1",
        "label_strategy": "weak-supervision-v1",
    }
    with artifact_path.open("wb") as handle:
        pickle.dump(payload, handle)

    metadata = load_artifact_metadata(artifact_path)

    assert metadata is not None
    assert metadata["model_version"] == "m1"
    assert metadata["feature_count"] == 1


def test_clear_ml_ranker_cache_is_callable() -> None:
    clear_ml_ranker_cache()
