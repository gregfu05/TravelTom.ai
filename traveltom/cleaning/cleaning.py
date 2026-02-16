"""Clean Yelp business snapshot and export a trimmed parquet.

Steps implemented from product guidance:
- Keep only open businesses (`is_open == 1`).
- Drop entries with missing lat/long and deduplicate on `business_id`.
- Enforce a review-count floor (default 10) to reduce noise.
- Compute a simple popularity signal: stars * log1p(review_count).
- Flatten key attributes, split categories, and engineer basic hour features.
- Drop address/state/postal_code; keep optional `city`/`name` for display.

Output: traveltom/datasets/business_SB_Cleaned.parquet
"""

from __future__ import annotations

import ast
from itertools import chain
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


REVIEW_FLOOR = 10
DATA_DIR = Path(__file__).resolve().parent.parent / "datasets"
RAW_PATH = DATA_DIR / "business_SB.parquet"
CLEAN_PATH = DATA_DIR / "business_SB_Cleaned.parquet"

# Attributes to surface as separate columns (add here as needed)
ATTRIBUTE_KEYS = [
    "RestaurantsPriceRange2",
    "OutdoorSeating",
    "GoodForKids",
    "Alcohol",
    "WiFi",
    "BikeParking",
    "BusinessParking",
    "GoodForGroups",
    "RestaurantsReservations",
]


def _parse_maybe_mapping(value) -> Dict:
    """Convert raw attributes/hours cell into a dict; tolerate NaNs/strings."""

    if isinstance(value, dict):
        return value
    if pd.isna(value):
        return {}
    try:
        parsed = ast.literal_eval(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, SyntaxError):
        return {}


def extract_attributes(df: pd.DataFrame) -> pd.DataFrame:
    attr_dicts = df.get("attributes", pd.Series(dtype=object)).apply(_parse_maybe_mapping)
    cols = {}
    for key in ATTRIBUTE_KEYS:
        cols[f"attr_{key}"] = attr_dicts.apply(lambda d: d.get(key))
    return pd.DataFrame(cols, index=df.index)


def split_categories(cat_value) -> List[str]:
    if pd.isna(cat_value):
        return []
    return [part.strip() for part in str(cat_value).split(",") if part.strip()]


def add_category_flags(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    cats = df["categories_list"]
    counts = pd.Series(chain.from_iterable(cats)).value_counts()
    top = counts.head(top_n).index
    for cat in top:
        df[f"cat_{cat.replace(' ', '_').replace('&', 'and')}"] = cats.apply(lambda lst: cat in lst)
    return df


def _range_minutes(range_str: str) -> int:
    """Return minutes open for a single range like '09:00-17:30'."""

    try:
        start_str, end_str = range_str.split("-")
        h1, m1 = [int(x) for x in start_str.split(":")]
        h2, m2 = [int(x) for x in end_str.split(":")]
    except ValueError:
        return 0
    start = h1 * 60 + m1
    end = h2 * 60 + m2
    if end < start:  # wraps past midnight
        end += 24 * 60
    return end - start


def hour_features(hours_value) -> Dict[str, int | bool]:
    hours = _parse_maybe_mapping(hours_value)
    if not hours:
        return {"weekly_open_minutes": 0, "weekend_open_minutes": 0, "late_night": False}

    weekly = 0
    weekend = 0
    late_night = False
    weekend_days = {"Saturday", "Sunday"}

    for day, ranges in hours.items():
        if pd.isna(ranges):
            continue
        day_minutes = 0
        for span in str(ranges).split(";"):
            span = span.strip()
            if not span:
                continue
            day_minutes += _range_minutes(span)
            try:
                _, end_str = span.split("-")
                h, m = [int(x) for x in end_str.split(":")]
                late_night |= h >= 23
            except ValueError:
                pass
        weekly += day_minutes
        if day in weekend_days:
            weekend += day_minutes

    return {
        "weekly_open_minutes": weekly,
        "weekend_open_minutes": weekend,
        "late_night": late_night,
    }


def clean_business_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Basic filters
    if "is_open" in df.columns:
        df = df[df["is_open"] == 1]
    df = df[df["review_count"].fillna(0) >= REVIEW_FLOOR]
    df = df.dropna(subset=["latitude", "longitude"], how="any")
    if "business_id" in df.columns:
        df = df.drop_duplicates(subset="business_id")

    # Popularity score
    df["popularity"] = df["stars"].fillna(0) * np.log1p(df["review_count"].fillna(0))

    # Attributes
    attr_df = extract_attributes(df)
    df = pd.concat([df, attr_df], axis=1)

    # Categories
    df["categories_list"] = df.get("categories", pd.Series(dtype=object)).apply(split_categories)
    df = add_category_flags(df)

    # Hours
    hours_features_df = df.get("hours", pd.Series(dtype=object)).apply(hour_features).apply(pd.Series)
    df = pd.concat([df, hours_features_df], axis=1)

    # Drop fields we don't need for modeling (keep city/name for display/filtering)
    drop_cols = [c for c in ["address", "state", "postal_code"] if c in df.columns]
    df = df.drop(columns=drop_cols, errors="ignore")

    return df


def main():
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Raw dataset not found at {RAW_PATH}")

    df = pd.read_parquet(RAW_PATH)
    cleaned = clean_business_df(df)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(CLEAN_PATH, index=False)
    print(f"Cleaned data written to {CLEAN_PATH} with {len(cleaned)} rows")


if __name__ == "__main__":
    main()
