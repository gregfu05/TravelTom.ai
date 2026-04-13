"""Step 4 ML ranker path for recommender_v3.

The ML ranker is swappable with the heuristic ranker:
- input: ranking feature frame + request context
- output: scored frame with `score_final`
"""

from __future__ import annotations

import logging
import os
import pickle
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from traveltom.recommendor.heuristic_ranker_v3 import HeuristicRankerV3
from traveltom.recommendor.ranking_features_v3 import (
    RANKING_FEATURE_COLUMNS,
    RankingFeatureContext,
)

logger = logging.getLogger(__name__)

ML_RANKER_BASE_VERSION = "ml-ranker-v3-lgbm-ltr"
MODEL_SCHEMA_VERSION = "ranking-features-v3-v1"
MODEL_FAMILY = "lightgbm-ltr"
DEFAULT_ML_MODEL_ARTIFACT_PATH = (
    Path(__file__).resolve().parent / "artifacts" / "ranker_v3_lgbm_ltr.pkl"
)

ML_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    column for column in RANKING_FEATURE_COLUMNS if column != "business_id"
)


@dataclass(frozen=True)
class MLRankerConfig:
    artifact_path: Path = field(default_factory=lambda: DEFAULT_ML_MODEL_ARTIFACT_PATH)
    ranker_version: str = ML_RANKER_BASE_VERSION
    schema_version: str = MODEL_SCHEMA_VERSION


@dataclass(frozen=True)
class MLRankerArtifact:
    model: Any
    feature_columns: tuple[str, ...]
    model_version: str
    model_family: str
    schema_version: str
    label_strategy: str


@dataclass(frozen=True)
class MLRankerOutput:
    scored: pd.DataFrame
    version: str
    used_fallback: bool = False
    fallback_reason: str | None = None


class LightGBMLTRRankerV3:
    """Runtime scorer backed by a persisted LightGBM ranking artifact."""

    def __init__(
        self,
        *,
        config: MLRankerConfig | None = None,
        fallback_ranker: HeuristicRankerV3 | None = None,
    ) -> None:
        self._config = config or MLRankerConfig()
        self._fallback_ranker = fallback_ranker or HeuristicRankerV3()
        self._artifact_cache: MLRankerArtifact | None = None
        self._artifact_attempted = False

    @property
    def version(self) -> str:
        return self._config.ranker_version

    @property
    def artifact_path(self) -> Path:
        return self._config.artifact_path

    def score(
        self,
        *,
        features: pd.DataFrame,
        context: RankingFeatureContext,
    ) -> MLRankerOutput:
        if features.empty:
            return MLRankerOutput(scored=features.copy(), version=self.version)

        artifact = self._load_artifact()
        if artifact is None:
            return self._fallback(
                features=features,
                context=context,
                reason="artifact_unavailable",
            )

        try:
            matrix = _build_model_matrix(
                features=features,
                feature_columns=artifact.feature_columns,
            )
            prediction = np.asarray(artifact.model.predict(matrix), dtype=np.float32).reshape(-1)
            if prediction.shape[0] != len(features):
                raise ValueError("prediction row count does not match feature rows")

            scored = _attach_heuristic_components(
                features=features,
                context=context,
                heuristic_ranker=self._fallback_ranker,
            )
            scored["score_ml"] = prediction
            scored["score_final"] = scored["score_ml"]
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

            return MLRankerOutput(
                scored=scored,
                version=f"{self.version}@{artifact.model_version}",
                used_fallback=False,
            )
        except Exception as exc:
            logger.exception(
                "ml_ranker_prediction_failed",
                extra={"artifact_path": str(self.artifact_path)},
            )
            return self._fallback(
                features=features,
                context=context,
                reason=f"prediction_failure:{exc.__class__.__name__}",
            )

    def _load_artifact(self) -> MLRankerArtifact | None:
        if self._artifact_attempted:
            return self._artifact_cache

        self._artifact_attempted = True
        path = self.artifact_path
        if not path.exists():
            self._artifact_cache = None
            return None

        try:
            with path.open("rb") as handle:
                payload = pickle.load(handle)
        except Exception:
            logger.exception(
                "ml_ranker_artifact_load_failed",
                extra={"artifact_path": str(path)},
            )
            self._artifact_cache = None
            return None

        artifact = _parse_artifact_payload(payload)
        if artifact is None:
            self._artifact_cache = None
            return None

        self._artifact_cache = artifact
        return artifact

    def _fallback(
        self,
        *,
        features: pd.DataFrame,
        context: RankingFeatureContext,
        reason: str,
    ) -> MLRankerOutput:
        heuristic_output = self._fallback_ranker.score(features=features, context=context)
        scored = heuristic_output.scored.copy()
        if "score_ml" not in scored.columns:
            scored["score_ml"] = np.nan

        return MLRankerOutput(
            scored=scored,
            version=f"{self.version}-fallback-{heuristic_output.version}",
            used_fallback=True,
            fallback_reason=reason,
        )


def load_artifact_metadata(path: Path) -> dict[str, Any] | None:
    """Read artifact metadata without creating a runtime ranker."""

    if not path.exists():
        return None

    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    feature_columns = payload.get("feature_columns")
    feature_count = len(feature_columns) if isinstance(feature_columns, (list, tuple)) else 0

    return {
        "model_version": str(payload.get("model_version", "")),
        "model_family": str(payload.get("model_family", "")),
        "schema_version": str(payload.get("schema_version", "")),
        "label_strategy": str(payload.get("label_strategy", "")),
        "feature_count": feature_count,
    }


def _parse_artifact_payload(payload: Any) -> MLRankerArtifact | None:
    if not isinstance(payload, dict):
        return None

    model = payload.get("model")
    feature_columns_raw = payload.get("feature_columns")
    model_version = str(payload.get("model_version", "")).strip()
    model_family = str(payload.get("model_family", "")).strip()
    schema_version = str(payload.get("schema_version", "")).strip()
    label_strategy = str(payload.get("label_strategy", "")).strip()

    if model is None or not callable(getattr(model, "predict", None)):
        return None
    if not isinstance(feature_columns_raw, (list, tuple)):
        return None

    feature_columns = tuple(
        str(column).strip() for column in feature_columns_raw if str(column).strip()
    )
    if not feature_columns:
        return None

    if schema_version and schema_version != MODEL_SCHEMA_VERSION:
        logger.warning(
            "ml_ranker_schema_mismatch",
            extra={
                "expected_schema": MODEL_SCHEMA_VERSION,
                "received_schema": schema_version,
            },
        )

    return MLRankerArtifact(
        model=model,
        feature_columns=feature_columns,
        model_version=model_version or "unknown",
        model_family=model_family or MODEL_FAMILY,
        schema_version=schema_version or MODEL_SCHEMA_VERSION,
        label_strategy=label_strategy or "unknown",
    )


def _build_model_matrix(
    *,
    features: pd.DataFrame,
    feature_columns: tuple[str, ...],
) -> pd.DataFrame:
    working = features.copy()
    for column in feature_columns:
        if column not in working.columns:
            working[column] = 0.0
    return (
        working[list(feature_columns)]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )


def _attach_heuristic_components(
    *,
    features: pd.DataFrame,
    context: RankingFeatureContext,
    heuristic_ranker: HeuristicRankerV3,
) -> pd.DataFrame:
    heuristic_scored = heuristic_ranker.score(features=features, context=context).scored
    component_columns = [
        "business_id",
        "score_quality",
        "score_relevance",
        "score_alignment",
        "score_geo",
        "score_operational",
        "score_completeness",
    ]

    available_columns = [column for column in component_columns if column in heuristic_scored]
    merged = features.copy().merge(
        heuristic_scored[available_columns],
        on="business_id",
        how="left",
    )

    for column in component_columns[1:]:
        if column not in merged.columns:
            merged[column] = 0.0

    merged[component_columns[1:]] = (
        merged[component_columns[1:]]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )
    return merged


def _resolved_artifact_path_from_env() -> Path:
    configured_path = os.getenv("TRAVELTOM_ML_RANKER_ARTIFACT_PATH", "").strip()
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return DEFAULT_ML_MODEL_ARTIFACT_PATH


@lru_cache(maxsize=16)
def _get_ml_ranker_for_path(path_value: str) -> LightGBMLTRRankerV3:
    config = MLRankerConfig(artifact_path=Path(path_value))
    return LightGBMLTRRankerV3(config=config)


def get_ml_ranker_from_env() -> LightGBMLTRRankerV3:
    """Return cached ML ranker, keyed by configured artifact path."""

    return _get_ml_ranker_for_path(str(_resolved_artifact_path_from_env()))


def clear_ml_ranker_cache() -> None:
    """Clear cached ML ranker instances (useful for tests)."""

    _get_ml_ranker_for_path.cache_clear()


__all__ = [
    "DEFAULT_ML_MODEL_ARTIFACT_PATH",
    "ML_FEATURE_COLUMNS",
    "ML_RANKER_BASE_VERSION",
    "MODEL_FAMILY",
    "MODEL_SCHEMA_VERSION",
    "LightGBMLTRRankerV3",
    "MLRankerConfig",
    "MLRankerOutput",
    "clear_ml_ranker_cache",
    "get_ml_ranker_from_env",
    "load_artifact_metadata",
]
