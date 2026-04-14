"""Seed `catalog_items` from the TravelTom master dataset.

The master dataset (traveltom_clean.parquet) contains ~149K rows across 61
cities from 4 sources (TBO Hotels, OpenStreetMap, Michelin, TripAdvisor).
Published on Kaggle as nicolsleyva/traveltommasterdataset.

Usage examples (run from repo root):
  python scripts/seed_catalog.py
  python scripts/seed_catalog.py \
    --dataset data/output/traveltom_clean.parquet
  python scripts/seed_catalog.py --dry-run
  python scripts/seed_catalog.py --truncate
  python scripts/seed_catalog.py --city Tokyo --city "New York"
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

# ── Dataset paths (priority order) ──────────────────────────────────────────
# 1. Post-processed clean parquet (from traveltom_postprocess.py)
# 2. Composite copy inside traveltom/datasets/
# 3. Legacy Yelp-only fallback (business_SB_Cleaned.parquet)
DEFAULT_DATASET = REPO_ROOT / "data" / "output" / "traveltom_clean.parquet"
COMPOSITE_DATASET = REPO_ROOT / "traveltom" / "datasets" / "Composite" / "traveltom_clean.parquet"
LEGACY_DATASET = REPO_ROOT / "traveltom" / "datasets" / "business_SB_Cleaned.parquet"

BUSINESS_ID_NAMESPACE = uuid.UUID("56f6e980-b2c0-4be2-a238-7176bf5a4fa7")

# ── Entity type → item_type mapping ─────────────────────────────────────────
ENTITY_TYPE_MAP = {
    "hotel": "hotel",
    "restaurant": "destination",
    "attraction": "destination",
}

# Fallback keyword classification (only used for legacy Yelp data)
HOTEL_KEYWORDS = (
    "hotel", "hotels", "hostel", "hostels", "resort", "resorts", "lodging",
    "bed and breakfast", "vacation rental", "vacation rentals",
    "guest house", "guest houses", "motel", "motels", "inn", "inns",
)
FLIGHT_KEYWORDS = (
    "airline", "airlines", "airport", "airports", "flight", "flights",
)

T = TypeVar("T")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed catalog_items from TravelTom master dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Path to source parquet dataset (auto-detected if omitted).",
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
        default=0,
        help="Drop rows below this review count (default 0 — keep all).",
    )
    parser.add_argument(
        "--city",
        action="append",
        dest="cities",
        help="Seed only specific city/cities (can repeat). Case-insensitive.",
    )
    parser.add_argument(
        "--entity-type",
        choices=["hotel", "restaurant", "attraction"],
        action="append",
        dest="entity_types",
        help="Seed only specific entity types (can repeat).",
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


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def _coerce_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _safe_str(value: Any) -> str | None:
    """Return a non-empty string or None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s if s and s.lower() != "nan" else None


def _safe_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _item_type_from_entity(entity_type: Any, tags: list[str] | None) -> str:
    """Determine item_type from the dataset's entity_type field.

    Falls back to keyword-based classification for legacy data that
    lacks the entity_type column.
    """
    if entity_type is not None and not pd.isna(entity_type):
        mapped = ENTITY_TYPE_MAP.get(str(entity_type).lower().strip())
        if mapped:
            return mapped

    # Legacy keyword fallback
    if not tags:
        return "destination"
    normalized = {t.casefold().strip() for t in tags}
    if any(kw in normalized for kw in FLIGHT_KEYWORDS):
        return "flight"
    if any(kw in normalized for kw in HOTEL_KEYWORDS):
        return "hotel"
    return "destination"


def _compute_popularity(raw: dict[str, Any]) -> float | None:
    pop = raw.get("popularity")
    if pop is not None and not pd.isna(pop):
        try:
            return float(pop)
        except (TypeError, ValueError):
            pass

    stars = raw.get("stars")
    review_count = raw.get("review_count")
    if stars is None or pd.isna(stars) or review_count is None or pd.isna(review_count):
        return None
    try:
        return round(float(stars) * float(np.log1p(float(review_count))), 3)
    except (TypeError, ValueError):
        return None


# ── Row preparation ──────────────────────────────────────────────────────────

def _is_new_schema(df: pd.DataFrame) -> bool:
    """Detect whether this is the new multi-city dataset (has entity_type + country)."""
    return "entity_type" in df.columns and "country" in df.columns


def _prepare_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    new_schema = _is_new_schema(df)
    rows: list[dict[str, Any]] = []

    for raw in df.to_dict(orient="records"):
        business_id = str(raw["business_id"])
        tags = _split_tags(raw.get("categories"))
        entity_type = raw.get("entity_type") if new_schema else None
        item_type = _item_type_from_entity(entity_type, tags)
        popularity = _compute_popularity(raw)

        # Price: use price_level directly (new schema) or extract from attributes
        if new_schema:
            price = _as_decimal(raw.get("price_level"))
        else:
            attrs = _coerce_dict(raw.get("attributes")) or {}
            price = _as_decimal(attrs.get("RestaurantsPriceRange2"))

        # Location country
        location_country = _safe_str(raw.get("country")) if new_schema else "US"

        # Build metadata payload
        metadata: dict[str, Any] = {
            "business_id": business_id,
            "review_count": _safe_int(raw.get("review_count")),
            "is_open": _safe_int(raw.get("is_open")),
            "popularity": popularity,
            "categories": _safe_str(raw.get("categories")),
        }

        if new_schema:
            # Rich metadata from the new multi-source dataset
            metadata.update({
                "entity_type": _safe_str(raw.get("entity_type")),
                "source": _safe_str(raw.get("source")),
                "continent": _safe_str(raw.get("continent")),
                "country_name": _safe_str(raw.get("country_name")),
                "state": _safe_str(raw.get("state")),
                "address": _safe_str(raw.get("address")),
                "description": _safe_str(raw.get("description")),
                "website": _safe_str(raw.get("website")),
                "phone": _safe_str(raw.get("phone")),
                "image_url": _safe_str(raw.get("image_url")),
                "attributes": _coerce_dict(raw.get("attributes")),
                "hours": _coerce_dict(raw.get("hours")),
            })
        else:
            # Legacy Yelp metadata
            metadata.update({
                "address": _safe_str(raw.get("address")),
                "state": _safe_str(raw.get("state")),
                "postal_code": _safe_str(raw.get("postal_code")),
                "attributes": _coerce_dict(raw.get("attributes")),
                "hours": _coerce_dict(raw.get("hours")),
            })

        # Strip None values from metadata to keep JSONB clean
        metadata = {k: v for k, v in metadata.items() if v is not None}

        rows.append(
            {
                "id": uuid.uuid5(BUSINESS_ID_NAMESPACE, business_id),
                "item_type": item_type,
                "name": str(raw.get("name") or business_id),
                "description": _safe_str(raw.get("description")) or _safe_str(raw.get("categories")),
                "location_city": _safe_str(raw.get("city")),
                "location_country": location_country,
                "latitude": _as_decimal(raw.get("latitude")),
                "longitude": _as_decimal(raw.get("longitude")),
                "price": price,
                "rating": _as_decimal(raw.get("stars")),
                "tags": tags,
                "metadata_json": metadata,
            }
        )
    return rows


# ── Filtering ────────────────────────────────────────────────────────────────

def _filter_source(
    df: pd.DataFrame,
    include_closed: bool,
    min_review_count: int,
    cities: list[str] | None,
    entity_types: list[str] | None,
) -> pd.DataFrame:
    working = df.copy()

    if not include_closed and "is_open" in working.columns:
        working = working[working["is_open"].fillna(1) == 1]

    if "review_count" in working.columns and min_review_count > 0:
        working = working[working["review_count"].fillna(0) >= min_review_count]

    if "business_id" in working.columns:
        working = working.drop_duplicates(subset="business_id")

    if cities:
        cities_lower = {c.lower() for c in cities}
        working = working[working["city"].str.lower().isin(cities_lower)]

    if entity_types and "entity_type" in working.columns:
        working = working[working["entity_type"].str.lower().isin(entity_types)]

    return working


# ── DB operations ────────────────────────────────────────────────────────────

async def _upsert_rows(
    rows: list[dict[str, Any]], batch_size: int, truncate: bool
) -> int:
    session_factory = get_session_factory()

    async with session_factory() as session:
        if truncate:
            await session.execute(delete(CatalogItem))

        inserted = 0
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
            inserted += len(batch)

        await session.commit()
        result = await session.execute(select(func.count()).select_from(CatalogItem))
        return int(result.scalar_one())


# ── Summary ──────────────────────────────────────────────────────────────────

def _print_summary(rows: list[dict[str, Any]], df: pd.DataFrame) -> None:
    by_type: dict[str, int] = {}
    for row in rows:
        by_type[row["item_type"]] = by_type.get(row["item_type"], 0) + 1

    print(f"\nPrepared rows: {len(rows):,}")
    print("Item types:")
    for itype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {itype:<16} {count:>8,}")

    if "city" in df.columns:
        print(f"\nCities:    {df['city'].nunique()}")
    if "country" in df.columns:
        print(f"Countries: {df['country'].nunique()}")
    if "source" in df.columns:
        print("\nBy source:")
        for src, count in df["source"].value_counts().items():
            print(f"  {src:<24} {count:>8,}")
    if "continent" in df.columns:
        print("\nBy continent:")
        for cont, count in df["continent"].value_counts().items():
            print(f"  {cont:<20} {count:>8,}")


# ── Dataset resolution ───────────────────────────────────────────────────────

def _resolve_dataset(explicit_path: Path | None) -> tuple[pd.DataFrame, str]:
    """Find and load the best available dataset.

    Priority:
      1. Explicit --dataset flag
      2. data/output/traveltom_clean.parquet  (post-processed master)
      3. traveltom/datasets/Composite/traveltom_clean.parquet
      4. traveltom/datasets/business_SB_Cleaned.parquet  (legacy Yelp)
    """
    if explicit_path is not None:
        p = explicit_path.resolve()
        if not p.exists():
            raise FileNotFoundError(f"Dataset not found: {p}")
        return pd.read_parquet(p), str(p)

    for path, label in [
        (DEFAULT_DATASET, "master (data/output)"),
        (COMPOSITE_DATASET, "master (Composite)"),
        (LEGACY_DATASET, "legacy Yelp (Santa Barbara)"),
    ]:
        resolved = path.resolve()
        if resolved.exists():
            tag = f"{resolved} [{label}]"
            print(f"Auto-detected dataset: {tag}")
            return pd.read_parquet(resolved), tag

    raise FileNotFoundError(
        "No dataset found. Run `python data/traveltom_build.py` + "
        "`python data/traveltom_postprocess.py`, or download from Kaggle "
        "(nicolsleyva/traveltommasterdataset) and place in data/output/."
    )


# ── Main ─────────────────────────────────────────────────────────────────────

async def main_async(args: argparse.Namespace) -> None:
    source, source_label = _resolve_dataset(args.dataset)

    is_new = _is_new_schema(source)
    print(f"Dataset:  {source_label}")
    print(f"Schema:   {'multi-city (new)' if is_new else 'Yelp legacy'}")
    print(f"Raw rows: {len(source):,}")

    filtered = _filter_source(
        source,
        include_closed=args.include_closed,
        min_review_count=args.min_review_count,
        cities=args.cities,
        entity_types=args.entity_types,
    )
    print(f"After filters: {len(filtered):,}")

    rows = _prepare_rows(filtered)
    _print_summary(rows, filtered)

    if args.dry_run:
        print("\nDry-run enabled. No database changes made.")
        return

    print(f"\nUpserting {len(rows):,} rows (batch size {args.batch_size})...")
    final_count = await _upsert_rows(
        rows=rows,
        batch_size=args.batch_size,
        truncate=args.truncate,
    )
    print(f"catalog_items row count after load: {final_count:,}")

    engine = get_engine()
    await engine.dispose()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
