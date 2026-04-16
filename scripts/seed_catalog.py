"""Seed `catalog_items` from the Yelp business CSV dataset.

Usage examples (run from repo root):
  python scripts/seed_catalog.py
  python scripts/seed_catalog.py \
    --dataset traveltom/datasets/traveltom_clean.csv
  python scripts/seed_catalog.py --dry-run
  python scripts/seed_catalog.py --truncate
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.models.catalog_item import CatalogItem  # noqa
from app.db.session import get_engine, get_session_factory  # noqa

# The clean snapshot CI deletes to force the fallback, then checks it was recreated.
DEFAULT_DATASET = (
    REPO_ROOT / "traveltom" / "datasets" / "composite" / "traveltom_clean2.csv"
)

# The authoritative raw CSV that is always committed and never deleted by CI.
DEFAULT_RAW_DATASET = (
    REPO_ROOT / "traveltom" / "datasets" / "composite" / "traveltom_clean.csv"
)

BUSINESS_ID_NAMESPACE = uuid.UUID("56f6e980-b2c0-4be2-a238-7176bf5a4fa7")

HOTEL_KEYWORDS = (
    "hotel",
    "hotels",
    "hostel",
    "hostels",
    "resort",
    "resorts",
    "lodging",
    "bed and breakfast",
    "vacation rental",
    "vacation rentals",
    "guest house",
    "guest houses",
    "motel",
    "motels",
    "inn",
    "inns",
)
RESTAURANT_KEYWORDS = (
    "restaurant",
    "restaurants",
    "food",
    "cafe",
    "cafes",
    "coffee",
    "brunch",
    "dinner",
    "breakfast",
)

T = TypeVar("T")


def _read_dataframe(file_path: Path) -> pd.DataFrame:
    """Read a CSV file into a DataFrame."""
    if file_path.suffix != ".csv":
        raise ValueError(f"Only CSV files are supported, got: {file_path.suffix}")
    return pd.read_csv(file_path, encoding="latin-1", on_bad_lines="skip")


def _load_source_dataset(dataset_path: Path) -> tuple[pd.DataFrame, str]:
    """
    Load the dataset at *dataset_path*.

    If the file is missing the function falls back to DEFAULT_RAW_DATASET,
    copies it to *dataset_path* so subsequent runs are fast,
    and prints the sentinel string that CI greps for.
    """
    if dataset_path.exists():
        return _read_dataframe(dataset_path), str(dataset_path)

    # --- fallback path ---------------------------------------------------
    if not DEFAULT_RAW_DATASET.exists():
        raise FileNotFoundError(f"Raw dataset not found: {DEFAULT_RAW_DATASET}")

    df = _read_dataframe(DEFAULT_RAW_DATASET)

    from shutil import copyfile

    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    copyfile(DEFAULT_RAW_DATASET, dataset_path)

    print("copied from raw snapshot")

    return df, "copied from raw snapshot"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed catalog_items from cleaned dataset."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--min-review-count", type=int, default=0)
    parser.add_argument("--truncate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _chunks(items: list[T], size: int) -> Iterator[list[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _as_decimal(value: Any) -> Decimal | None:
    try:
        if value is None or pd.isna(value):
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def _split_tags(value: Any) -> list[str] | None:
    if value is None or pd.isna(value):
        return None
    return [v.strip() for v in str(value).split(",") if v.strip()] or None


HOTEL_KEYWORDS = ("hotel", "hostel", "resort", "lodging", "inn", "motel")
FLIGHT_KEYWORDS = ("airline", "airport", "flight")

# Tags that are too generic to signal a specific item type.
_GENERIC_BUCKETS = {"hotels and travel", "travel"}


def _normalize_tag(value: str) -> str:
    return " ".join(value.lower().replace("&", " and ").split())


def _item_type_from_tags(tags: list[str] | None) -> str:
    """
    Classify a list of tags into "hotel", "flight", or "destination".

    Generic tags like "Hotels & Travel" (normalises to "hotels and travel")
    are ignored so they don't accidentally match the hotel keywords.

    Examples
    --------
    ["Hotels", "Restaurants"] → "hotel"
    ["Airports", "Travel"]    → "flight"
    ["Hotels & Travel"]       → "destination"   # generic-only → falls through
    """
    if not tags:
        return "destination"

    normalized = [_normalize_tag(tag) for tag in tags]
    filtered = [t for t in normalized if t not in _GENERIC_BUCKETS]

    if any(any(k in tag for k in FLIGHT_KEYWORDS) for tag in filtered):
        return "flight"

    if any(any(k in tag for k in HOTEL_KEYWORDS) for tag in filtered):
        return "hotel"

    return "destination"


def _item_type(raw: dict[str, Any]) -> str:
    et = str(raw.get("entity_type") or "").lower()
    if et in {"hotel", "lodging"}:
        return "hotel"
    if et in {"flight", "airport", "airline"}:
        return "flight"
    return "destination"


def _normalize_tag(value: str) -> str:
    normalized = value.casefold().strip()
    normalized = normalized.replace("&", " and ")
    normalized = " ".join(normalized.split())
    return normalized


def _price_from_attributes(attributes: dict[str, Any]) -> Decimal | None:
    raw = attributes.get("RestaurantsPriceRange2")
    return _as_decimal(raw)


def _extract_category_flags(raw: dict[str, Any]) -> dict[str, bool] | None:
    flags: dict[str, bool] = {}
    for key, value in raw.items():
        if not key.startswith("cat_"):
            continue
        if pd.isna(value):
            continue
        flags[key] = bool(value)
    return flags or None


def _compute_popularity(raw: dict[str, Any]) -> float | None:
    for key in ("popularity", "popularity_norm", "quality_score"):
        value = raw.get(key)
        if value is None or pd.isna(value):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    stars = raw.get("stars")
    review_count = raw.get("review_count")
    if stars is None or pd.isna(stars) or review_count is None or pd.isna(review_count):
        return None

    try:
        return float(stars) * float(np.log1p(float(review_count)))
    except (TypeError, ValueError):
        return None


def _prepare_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Convert a DataFrame into a list of dicts ready for upsert.

    Rows with a missing or null ``business_id`` are skipped.  A
    ``ValueError`` is raised early if the column is absent entirely so the
    error is obvious rather than surfacing as a ``KeyError`` mid-loop.
    """
    if "business_id" not in df.columns:
        raise ValueError(
            "Missing required column: business_id\n"
            f"Available columns: {list(df.columns)}"
        )

    rows: list[dict[str, Any]] = []

    for raw in df.to_dict(orient="records"):
        business_id = raw.get("business_id")

        # Skip rows with a missing or NaN business_id safely.
        if business_id is None or pd.isna(business_id):
            continue

        business_id = str(business_id)

        rows.append(
            {
                "id": uuid.uuid5(BUSINESS_ID_NAMESPACE, business_id),
                "item_type": item_type,
                "name": str(raw.get("name") or business_id),
                "description": description,
                "location_city": (
                    str(raw["city"])
                    if raw.get("city") is not None and not pd.isna(raw.get("city"))
                    else None
                ),
                "location_country": location_country,
                "item_type": _item_type(raw),
                "name": _safe_str(raw.get("name")) or business_id,
                "description": _safe_str(
                    raw.get("description_clean") or raw.get("description")
                ),
                "location_city": _safe_str(raw.get("city")),
                "location_country": _safe_str(raw.get("country")) or "US",
                "latitude": _as_decimal(raw.get("latitude")),
                "longitude": _as_decimal(raw.get("longitude")),
                "price": None,
                "rating": _as_decimal(raw.get("stars")),
                "tags": _split_tags(raw.get("categories_clean")),
                "metadata_json": {
                    "business_id": business_id,
                    "address": raw.get("address"),
                    "state": raw.get("state"),
                    "postal_code": raw.get("postal_code"),
                    "categories": raw.get("categories"),
                    "review_count": (
                        int(raw["review_count"])
                        if raw.get("review_count") is not None
                        and not pd.isna(raw.get("review_count"))
                        else None
                    ),
                    "is_open": (
                        int(raw["is_open"])
                        if raw.get("is_open") is not None
                        and not pd.isna(raw.get("is_open"))
                        else None
                    ),
                    "popularity": popularity,
                    "attributes": attributes or None,
                    "hours": _coerce_hours(raw.get("hours")),
                    "category_flags": category_flags,
                    "entity_type": entity_type,
                    "source": source,
                    "source": raw.get("source"),
                    "entity_type": raw.get("entity_type"),
                    "review_count": (
                        int(raw["review_count"])
                        if raw.get("review_count") is not None
                        and not pd.isna(raw.get("review_count"))
                        else None
                    ),
                    "popularity": (
                        float(raw["popularity"])
                        if raw.get("popularity") is not None
                        and not pd.isna(raw.get("popularity"))
                        else None
                    ),
                    "quality_score": raw.get("quality_score"),
                    "stars_norm": raw.get("stars_norm"),
                    "review_count_norm": raw.get("review_count_norm"),
                    "popularity_norm": raw.get("popularity_norm"),
                },
            }
        )

    return rows


def _filter_source(
    df: pd.DataFrame, include_closed: bool, min_review_count: int
) -> pd.DataFrame:
    working = df.copy()

    if not include_closed and "is_open" in working.columns:
        working = working[working["is_open"] == 1]
    if min_review_count > 0:
        if "review_count" in working.columns:
            review_signal = pd.to_numeric(
                working["review_count"], errors="coerce"
            ).fillna(0)
            working = working[review_signal >= min_review_count]
        elif "review_count_norm" in working.columns:
            review_signal = pd.to_numeric(
                working["review_count_norm"], errors="coerce"
            ).fillna(0)
            working = working[review_signal >= 0]
    if "business_id" in working.columns:
        working = working.drop_duplicates(subset="business_id")

    return working
def _filter(df: pd.DataFrame, min_review_count: int) -> pd.DataFrame:
    working = df.copy()

    if "business_id" in working.columns:
        working = working.drop_duplicates(subset="business_id")

    if "review_count" in working.columns and min_review_count > 0:
        working = working[working["review_count"].fillna(0) >= min_review_count]

    return working


async def _upsert(rows: list[dict[str, Any]], batch_size: int, truncate: bool) -> int:
    session_factory = get_session_factory()

    async with session_factory() as session:
        if truncate:
            await session.execute(delete(CatalogItem))

        for batch in _chunks(rows, batch_size):
            stmt = insert(CatalogItem).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=[CatalogItem.id],
                set_={
                    "item_type": stmt.excluded.item_type,
                    "name": stmt.excluded.name,
                    "description": stmt.excluded.description,
                    "location_city": stmt.excluded.location_city,
                    "location_country": stmt.excluded.location_country,
                    "latitude": stmt.excluded.latitude,
                    "longitude": stmt.excluded.longitude,
                    "price": stmt.excluded.price,
                    "rating": stmt.excluded.rating,
                    "tags": stmt.excluded.tags,
                    "metadata_json": stmt.excluded.metadata_json,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)

        await session.commit()

        result = await session.execute(select(func.count()).select_from(CatalogItem))
        return int(result.scalar_one())


async def main_async(args: argparse.Namespace) -> None:
    # Single load — fallback + "copied from raw snapshot" print happen inside.
    df, label = _load_source_dataset(args.dataset)
    print(f"Dataset: {label}")

    df = _filter(df, args.min_review_count)
    rows = _prepare_rows(df)
    print(f"Rows to insert: {len(rows)}")

    if args.dry_run:
        print("Dry run complete.")
        return

    count = await _upsert(rows, args.batch_size, args.truncate)
    print(f"Final row count: {count}")

    engine = get_engine()
    await engine.dispose()


def main() -> int:
    args = parse_args()
    asyncio.run(main_async(args))


def _read_dataframe(file_path: Path) -> pd.DataFrame:
    """Read a DataFrame from various file formats."""
    if file_path.suffix == ".csv":
        return pd.read_csv(file_path)
    elif file_path.suffix == ".parquet":
        return pd.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")


def _load_source_dataset(dataset_path: Path) -> tuple[pd.DataFrame, str]:
    if dataset_path.exists():
        return _read_dataframe(dataset_path), str(dataset_path)

    default_clean_path = DEFAULT_DATASET.resolve()
    if dataset_path != default_clean_path:
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    if not DEFAULT_RAW_DATASET.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path} and raw fallback missing: "
            f"{DEFAULT_RAW_DATASET.resolve()}"
        )

    # Fast bootstrap fallback: mirror raw snapshot to the cleaned path.
    default_clean_path.parent.mkdir(parents=True, exist_ok=True)
    copyfile(DEFAULT_RAW_DATASET, default_clean_path)
    return (
        _read_dataframe(default_clean_path),
        f"{default_clean_path} (copied from raw snapshot)",
    )


if __name__ == "__main__":
    raise SystemExit(main())
