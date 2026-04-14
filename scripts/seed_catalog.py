"""Seed `catalog_items` from the TravelTom clean CSV dataset.

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

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.models.catalog_item import CatalogItem  # noqa: E402
from app.db.session import get_engine, get_session_factory  # noqa: E402

DEFAULT_DATASET = REPO_ROOT / "traveltom" / "datasets" / "traveltom_clean.csv"
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
FLIGHT_KEYWORDS = (
    "airline",
    "airlines",
    "airport",
    "airports",
    "flight",
    "flights",
)

T = TypeVar("T")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed catalog_items from TravelTom clean CSV."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to source CSV dataset (defaults to traveltom_clean.csv).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows per upsert batch.",
    )
    parser.add_argument(
        "--min-review-count",
        type=int,
        default=10,
        help="Drop rows below this review count.",
    )
    parser.add_argument(
        "--include-closed",
        action="store_true",
        help="Include businesses with is_open != 1.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete all existing catalog_items rows before insert/upsert.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing to the database.",
    )
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be > 0")
    if args.min_review_count < 0:
        parser.error("--min-review-count must be >= 0")
    return args


def _chunks(items: list[T], size: int) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _split_tags(categories: Any) -> list[str] | None:
    if isinstance(categories, (list, tuple, set, np.ndarray, pd.Series)):
        tags = [str(part).strip() for part in categories if str(part).strip()]
        return tags or None
    if categories is None:
        return None
    if pd.isna(categories):
        return None
    tags = [part.strip() for part in str(categories).split(",") if part.strip()]
    return tags or None


def _coerce_attributes(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _coerce_hours(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _coerce_flag(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value) > 0
    if isinstance(value, str):
        lowered = value.strip().casefold()
        return lowered in {"1", "true", "yes", "y"}
    return False


def _synthetic_business_id(raw: dict[str, Any], index: int) -> str:
    name = str(raw.get("name") or "").strip().casefold()
    city = str(raw.get("city") or "").strip().casefold()
    country = str(raw.get("country") or "").strip().casefold()
    latitude = str(raw.get("latitude") or "").strip()
    longitude = str(raw.get("longitude") or "").strip()
    return "|".join((name, city, country, latitude, longitude, str(index)))


def _entity_type_from_row(raw: dict[str, Any]) -> str:
    entity_type = str(raw.get("entity_type") or "").strip().casefold()
    if entity_type:
        if entity_type.endswith("s"):
            entity_type = entity_type[:-1]
        return entity_type
    if _coerce_flag(raw.get("entity_type_flight")):
        return "flight"
    if _coerce_flag(raw.get("entity_type_hotel")):
        return "hotel"
    if _coerce_flag(raw.get("entity_type_restaurant")):
        return "restaurant"
    if _coerce_flag(raw.get("entity_type_attraction")):
        return "attraction"
    return "destination"


def _source_from_row(raw: dict[str, Any]) -> str | None:
    source = str(raw.get("source") or "").strip()
    if source:
        return source
    if _coerce_flag(raw.get("source_tbo_hotels")):
        return "tbo_hotels"
    if _coerce_flag(raw.get("source_tripadvisor")):
        return "tripadvisor"
    if _coerce_flag(raw.get("source_openstreetmap")):
        return "openstreetmap"
    return None


def _description_from_row(raw: dict[str, Any]) -> str | None:
    for key in ("description", "description_clean"):
        value = raw.get(key)
        if value is None or pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _rating_from_row(raw: dict[str, Any]) -> Decimal | None:
    rating = _as_decimal(raw.get("stars"))
    if rating is not None:
        return rating

    stars_norm = raw.get("stars_norm")
    if stars_norm is None or pd.isna(stars_norm):
        return None
    try:
        # TravelTom clean snapshots may provide normalized z-scores only.
        value = float(stars_norm)
    except (TypeError, ValueError):
        return None

    # Map common z-score range to a rough [0, 5] star scale.
    clipped = min(max(value, -2.5), 2.5)
    scaled = ((clipped + 2.5) / 5.0) * 5.0
    return _as_decimal(round(scaled, 2))


def _item_type_from_tags(tags: list[str] | None) -> str:
    if not tags:
        return "destination"

    normalized_tags = {_normalize_tag(tag) for tag in tags}
    if any(tag in FLIGHT_KEYWORDS for tag in normalized_tags):
        return "flight"
    if any(tag in HOTEL_KEYWORDS for tag in normalized_tags):
        return "hotel"
    return "destination"


def _item_type_from_row(raw: dict[str, Any], tags: list[str] | None) -> str:
    entity_type = _entity_type_from_row(raw)
    if entity_type in {"hotel", "flight"}:
        return entity_type
    if entity_type in {"restaurant", "attraction", "destination"}:
        return "destination"
    return _item_type_from_tags(tags)


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
    rows: list[dict[str, Any]] = []

    for index, raw in enumerate(df.to_dict(orient="records")):
        business_id = str(raw.get("business_id") or _synthetic_business_id(raw, index))
        tags = (
            _split_tags(raw.get("categories_list"))
            or _split_tags(raw.get("categories"))
            or _split_tags(raw.get("categories_clean"))
        )
        if tags is None and isinstance(raw.get("categories_clean"), str):
            tags = _split_tags(str(raw.get("categories_clean")).replace(";", ","))

        inferred_attributes = {
            key.removeprefix("attr_"): bool(value)
            for key, value in raw.items()
            if key.startswith("attr_") and value is not None and not pd.isna(value)
        }
        attributes = _coerce_attributes(raw.get("attributes"))
        if inferred_attributes:
            attributes = {**attributes, **inferred_attributes}

        category_flags = _extract_category_flags(raw)
        popularity = _compute_popularity(raw)
        entity_type = _entity_type_from_row(raw)
        item_type = _item_type_from_row(raw, tags)
        source = _source_from_row(raw)
        description = _description_from_row(raw)

        location_country = (
            str(raw["country"])
            if raw.get("country") is not None and not pd.isna(raw.get("country"))
            else (
                str(raw["country_name"])
                if raw.get("country_name") is not None
                and not pd.isna(raw.get("country_name"))
                else None
            )
        )

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
                "latitude": _as_decimal(raw.get("latitude")),
                "longitude": _as_decimal(raw.get("longitude")),
                "price": _price_from_attributes(attributes),
                "rating": _rating_from_row(raw),
                "tags": tags,
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


async def _upsert_rows(
    rows: list[dict[str, Any]], batch_size: int, truncate: bool
) -> int:
    session_factory = get_session_factory()

    async with session_factory() as session:
        if truncate:
            await session.execute(delete(CatalogItem))

        for batch in _chunks(rows, batch_size):
            stmt = insert(CatalogItem).values(batch)
            upsert_stmt = stmt.on_conflict_do_update(
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
            await session.execute(upsert_stmt)

        await session.commit()
        result = await session.execute(select(func.count()).select_from(CatalogItem))
        return int(result.scalar_one())


def _print_summary(rows: list[dict[str, Any]]) -> None:
    by_type: dict[str, int] = {"destination": 0, "hotel": 0, "flight": 0}
    for row in rows:
        by_type[row["item_type"]] = by_type.get(row["item_type"], 0) + 1

    print(f"Prepared rows: {len(rows)}")
    print("Item types:")
    print(f"  destination: {by_type.get('destination', 0)}")
    print(f"  hotel: {by_type.get('hotel', 0)}")
    print(f"  flight: {by_type.get('flight', 0)}")


async def main_async(args: argparse.Namespace) -> None:
    dataset_path = args.dataset.resolve()
    source, source_label = _load_source_dataset(dataset_path)
    filtered = _filter_source(
        source,
        include_closed=args.include_closed,
        min_review_count=args.min_review_count,
    )
    rows = _prepare_rows(filtered)

    print(f"Dataset: {source_label}")
    print(f"Input rows: {len(source)}")
    print(f"Rows after filters: {len(filtered)}")
    _print_summary(rows)

    if args.dry_run:
        print("Dry-run enabled. No database changes made.")
        return

    final_count = await _upsert_rows(
        rows=rows,
        batch_size=args.batch_size,
        truncate=args.truncate,
    )
    print(f"catalog_items row count after load: {final_count}")

    engine = get_engine()
    await engine.dispose()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


def _load_source_dataset(dataset_path: Path) -> tuple[pd.DataFrame, str]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    suffix = dataset_path.suffix.casefold()
    if suffix != ".csv":
        raise ValueError(
            "Only CSV datasets are supported for seeding. " f"Received: {dataset_path}"
        )
    return pd.read_csv(dataset_path, low_memory=False), str(dataset_path)


if __name__ == "__main__":
    main()
