#!/usr/bin/env python3
"""
TravelTom Post-Processor
=========================
Takes the raw 831K parquet and produces a clean, polished final dataset.

Fixes:
  1. Normalizes city names (merges "London_England" into "London", etc.)
  2. Assigns every row to nearest target city using coordinates
  3. Fills missing star ratings using hotel star classification + medians
  4. Removes junk rows (no name, no coords, duplicates)
  5. Recomputes popularity scores
  6. Exports clean parquet + CSV + updated stats

Usage:
  python traveltom_postprocess.py
"""

import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm

INPUT = Path("output/traveltom_full.parquet")
OUTPUT_DIR = Path("output")

# ── Target cities with coordinates ──────────────────────────────────────────
TARGET_CITIES = {
    "London":        (51.51, -0.13, "GB", "Europe"),
    "Paris":         (48.86, 2.35, "FR", "Europe"),
    "Rome":          (41.90, 12.50, "IT", "Europe"),
    "Barcelona":     (41.39, 2.17, "ES", "Europe"),
    "Amsterdam":     (52.37, 4.90, "NL", "Europe"),
    "Prague":        (50.08, 14.42, "CZ", "Europe"),
    "Vienna":        (48.21, 16.37, "AT", "Europe"),
    "Berlin":        (52.52, 13.40, "DE", "Europe"),
    "Istanbul":      (41.01, 28.98, "TR", "Europe"),
    "Lisbon":        (38.72, -9.14, "PT", "Europe"),
    "Madrid":        (40.42, -3.70, "ES", "Europe"),
    "Athens":        (37.98, 23.73, "GR", "Europe"),
    "Dublin":        (53.35, -6.26, "IE", "Europe"),
    "Budapest":      (47.50, 19.04, "HU", "Europe"),
    "Edinburgh":     (55.95, -3.19, "GB", "Europe"),
    "Florence":      (43.77, 11.25, "IT", "Europe"),
    "Munich":        (48.14, 11.58, "DE", "Europe"),
    "Copenhagen":    (55.68, 12.57, "DK", "Europe"),
    "Stockholm":     (59.33, 18.07, "SE", "Europe"),
    "Milan":         (45.46, 9.19, "IT", "Europe"),
    "Porto":         (41.15, -8.61, "PT", "Europe"),
    "Seville":       (37.39, -5.98, "ES", "Europe"),
    "Tokyo":         (35.68, 139.69, "JP", "Asia"),
    "Bangkok":       (13.76, 100.50, "TH", "Asia"),
    "Singapore":     (1.35, 103.82, "SG", "Asia"),
    "Hong Kong":     (22.32, 114.17, "HK", "Asia"),
    "Seoul":         (37.57, 126.98, "KR", "Asia"),
    "Kuala Lumpur":  (3.14, 101.69, "MY", "Asia"),
    "Bali":          (-8.41, 115.19, "ID", "Asia"),
    "Delhi":         (28.61, 77.21, "IN", "Asia"),
    "Mumbai":        (19.08, 72.88, "IN", "Asia"),
    "Kyoto":         (35.01, 135.77, "JP", "Asia"),
    "Shanghai":      (31.23, 121.47, "CN", "Asia"),
    "Beijing":       (39.90, 116.40, "CN", "Asia"),
    "Hanoi":         (21.03, 105.85, "VN", "Asia"),
    "Taipei":        (25.03, 121.57, "TW", "Asia"),
    "Chiang Mai":    (18.79, 98.98, "TH", "Asia"),
    "Dubai":         (25.20, 55.27, "AE", "Asia"),
    "Amman":         (31.95, 35.93, "JO", "Asia"),
    "New York":      (40.71, -74.01, "US", "North America"),
    "Los Angeles":   (34.05, -118.24, "US", "North America"),
    "San Francisco": (37.77, -122.42, "US", "North America"),
    "Miami":         (25.76, -80.19, "US", "North America"),
    "Mexico City":   (19.43, -99.13, "MX", "North America"),
    "Cancun":        (21.16, -86.85, "MX", "North America"),
    "Toronto":       (43.65, -79.38, "CA", "North America"),
    "Vancouver":     (49.28, -123.12, "CA", "North America"),
    "Buenos Aires":  (-34.60, -58.38, "AR", "South America"),
    "Rio de Janeiro":(-22.91, -43.17, "BR", "South America"),
    "Lima":          (-12.05, -77.04, "PE", "South America"),
    "Bogota":        (4.71, -74.07, "CO", "South America"),
    "Cusco":         (-13.53, -71.97, "PE", "South America"),
    "Havana":        (23.11, -82.37, "CU", "North America"),
    "Cape Town":     (-33.93, 18.42, "ZA", "Africa"),
    "Cairo":         (30.04, 31.24, "EG", "Africa"),
    "Nairobi":       (-1.29, 36.82, "KE", "Africa"),
    "Marrakech":     (31.63, -7.98, "MA", "Africa"),
    "Johannesburg":  (-26.20, 28.05, "ZA", "Africa"),
    "Sydney":        (-33.87, 151.21, "AU", "Oceania"),
    "Melbourne":     (-37.81, 144.96, "AU", "Oceania"),
    "Auckland":      (-36.85, 174.76, "NZ", "Oceania"),
}

# Pre-compute numpy arrays for fast distance calc
_city_names = list(TARGET_CITIES.keys())
_city_lats = np.array([v[0] for v in TARGET_CITIES.values()])
_city_lngs = np.array([v[1] for v in TARGET_CITIES.values()])
_city_cc = [v[2] for v in TARGET_CITIES.values()]
_city_cont = [v[3] for v in TARGET_CITIES.values()]

# Max distance in degrees to assign to a target city (~100km)
MAX_DIST_DEG = 1.0


def nearest_city(lat, lng):
    """Find nearest target city. Returns (name, country, continent, dist) or None."""
    if pd.isna(lat) or pd.isna(lng):
        return None
    dists = np.sqrt((_city_lats - lat)**2 + (_city_lngs - lng)**2)
    idx = np.argmin(dists)
    if dists[idx] <= MAX_DIST_DEG:
        return (_city_names[idx], _city_cc[idx], _city_cont[idx], dists[idx])
    return None


def main():
    print("Loading dataset...")
    df = pd.read_parquet(INPUT)
    print(f"Loaded: {len(df):,} rows")
    original = len(df)

    # ═══════════════════════════════════════════════════════════════════════
    # FIX 1: Assign every row to nearest target city using coordinates
    # ═══════════════════════════════════════════════════════════════════════
    print("\n[1/6] Assigning rows to target cities by coordinates...")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    has_coords = df["latitude"].notna() & df["longitude"].notna()
    print(f"  Rows with coords: {has_coords.sum():,} / {len(df):,}")

    # Vectorized nearest city assignment (batch)
    new_city = []
    new_cc = []
    new_cont = []
    assigned = 0

    lats = df["latitude"].values
    lngs = df["longitude"].values

    for i in tqdm(range(len(df)), desc="  Geo-assign"):
        if pd.isna(lats[i]) or pd.isna(lngs[i]):
            new_city.append(None)
            new_cc.append(None)
            new_cont.append(None)
            continue
        result = nearest_city(lats[i], lngs[i])
        if result:
            new_city.append(result[0])
            new_cc.append(result[1])
            new_cont.append(result[2])
            assigned += 1
        else:
            new_city.append(None)
            new_cc.append(None)
            new_cont.append(None)

    df["target_city"] = new_city
    df["_cc"] = new_cc
    df["_cont"] = new_cont

    # Use target_city as the clean city name where assigned
    mask = df["target_city"].notna()
    df.loc[mask, "city"] = df.loc[mask, "target_city"]
    df.loc[mask, "country"] = df.loc[mask, "_cc"]
    df.loc[mask, "continent"] = df.loc[mask, "_cont"]

    print(f"  Assigned to target cities: {assigned:,}")
    print(f"  Not near any target: {len(df) - assigned:,}")

    # Drop rows not near any target city (they're noise like Usedom)
    df_target = df[df["target_city"].notna()].copy()
    df_other = df[df["target_city"].isna()].copy()
    print(f"  Keeping target city rows: {len(df_target):,}")
    print(f"  Keeping other rows (no coords or far from targets): {len(df_other):,}")

    # Keep "other" rows only if they have a matching city name
    target_names_lower = {c.lower() for c in TARGET_CITIES}
    df_other_match = df_other[df_other["city"].str.lower().str.strip().isin(target_names_lower)]
    print(f"  Other rows matching target city by name: {len(df_other_match):,}")

    df = pd.concat([df_target, df_other_match], ignore_index=True)
    df = df.drop(columns=["target_city", "_cc", "_cont"], errors="ignore")
    print(f"  After geo-filter: {len(df):,} rows")

    # ═══════════════════════════════════════════════════════════════════════
    # FIX 2: Fix star ratings
    # ═══════════════════════════════════════════════════════════════════════
    print("\n[2/6] Fixing star ratings...")
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")

    # TBO hotels: HotelRating is classification (1-5 stars), not guest review
    # These are valid star ratings — keep them
    tbo_mask = df["source"] == "tbo_hotels"
    tbo_with_stars = tbo_mask & df["stars"].notna() & (df["stars"] >= 1) & (df["stars"] <= 5)
    print(f"  TBO hotels with valid star rating: {tbo_with_stars.sum():,}")

    # For rows without stars: assign based on entity type median
    for etype in df["entity_type"].unique():
        mask = (df["entity_type"] == etype) & df["stars"].isna()
        median = df.loc[(df["entity_type"] == etype) & df["stars"].notna(), "stars"].median()
        if not pd.isna(median):
            df.loc[mask, "stars"] = round(median, 1)
            print(f"  Filled {mask.sum():,} {etype} rows with median {median:.1f}")

    # Clamp to 1-5
    df["stars"] = df["stars"].clip(1.0, 5.0)
    print(f"  Stars coverage: {df['stars'].notna().mean():.1%}")

    # ═══════════════════════════════════════════════════════════════════════
    # FIX 3: Remove junk rows
    # ═══════════════════════════════════════════════════════════════════════
    print("\n[3/6] Removing junk rows...")
    before = len(df)

    # Drop no-name
    df = df[df["name"].notna() & (df["name"].str.strip() != "") & (df["name"] != "nan")]

    # Drop rows with clearly bad names (single character, numbers only)
    df = df[df["name"].str.len() >= 3]
    df = df[~df["name"].str.match(r'^\d+$', na=False)]

    print(f"  Removed {before - len(df):,} junk rows")

    # ═══════════════════════════════════════════════════════════════════════
    # FIX 4: Deduplicate
    # ═══════════════════════════════════════════════════════════════════════
    print("\n[4/6] Deduplicating...")
    before = len(df)

    df["_name_key"] = df["name"].str.lower().str.strip()
    df["_city_key"] = df["city"].str.lower().str.strip()

    # Priority: michelin > tripadvisor > osm > kaggle > tbo
    priority = {"michelin": 0, "tripadvisor": 1, "openstreetmap": 2,
                "kaggle_destinations": 3, "kaggle_global": 4, "kaggle_famous": 5,
                "tbo_hotels": 6}
    df["_pri"] = df["source"].map(priority).fillna(5)
    df = df.sort_values("_pri")

    # Dedup by name + city
    df = df.drop_duplicates(subset=["_name_key", "_city_key"], keep="first")

    # Also dedup by name + rounded coords
    has_coords = df["latitude"].notna() & df["longitude"].notna()
    df_c = df[has_coords].copy()
    df_nc = df[~has_coords].copy()
    if len(df_c) > 0:
        df_c["_lr"] = (df_c["latitude"] * 100).round() / 100
        df_c["_lnr"] = (df_c["longitude"] * 100).round() / 100
        df_c = df_c.drop_duplicates(["_name_key", "_lr", "_lnr"], keep="first")
        df_c = df_c.drop(columns=["_lr", "_lnr"])
    df = pd.concat([df_c, df_nc], ignore_index=True)

    df = df.drop(columns=["_name_key", "_city_key", "_pri"], errors="ignore")
    print(f"  Deduped: {before:,} -> {len(df):,}")

    # ═══════════════════════════════════════════════════════════════════════
    # FIX 5: Recompute features
    # ═══════════════════════════════════════════════════════════════════════
    print("\n[5/6] Computing features...")
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0).astype(int)
    df["popularity"] = df["stars"] * np.log1p(df["review_count"])
    df["popularity"] = df["popularity"].round(3)

    # Regenerate business_id
    import hashlib
    df["business_id"] = df.apply(
        lambda r: hashlib.sha256(
            f"{str(r['name']).lower().strip()}|{r['latitude']}|{r['longitude']}".encode()
        ).hexdigest()[:16], axis=1
    )

    # ═══════════════════════════════════════════════════════════════════════
    # FIX 6: Export
    # ═══════════════════════════════════════════════════════════════════════
    print("\n[6/6] Exporting...")

    pq = OUTPUT_DIR / "traveltom_clean.parquet"
    df.to_parquet(pq, compression="zstd", index=False)
    print(f"  traveltom_clean.parquet: {pq.stat().st_size / 1024 / 1024:.1f} MB")

    csv = OUTPUT_DIR / "traveltom_clean.csv"
    df.to_csv(csv, index=False)
    print(f"  traveltom_clean.csv: {csv.stat().st_size / 1024 / 1024:.1f} MB")

    # Stats
    stats = {
        "total_rows": len(df),
        "original_rows": original,
        "unique_cities": int(df["city"].nunique()),
        "unique_countries": int(df["country"].nunique()),
        "by_source": df["source"].value_counts().to_dict(),
        "by_entity_type": df["entity_type"].value_counts().to_dict(),
        "by_continent": df["continent"].value_counts().to_dict(),
        "by_city": df["city"].value_counts().head(30).to_dict(),
        "stars_coverage": f"{df['stars'].notna().mean():.1%}",
        "coords_coverage": f"{df['latitude'].notna().mean():.1%}",
        "avg_stars": round(df["stars"].mean(), 2),
        "avg_review_count": round(df["review_count"].mean(), 1),
    }
    stats_path = OUTPUT_DIR / "stats_clean.json"
    stats_path.write_text(json.dumps(stats, indent=2, default=str))

    print("\n" + "=" * 55)
    print("  FINAL CLEAN DATASET")
    print("=" * 55)
    print(f"  Rows:           {len(df):>10,}")
    print(f"  Cities:         {df['city'].nunique():>10}")
    print(f"  Countries:      {df['country'].nunique():>10}")
    print(f"  Hotels:         {len(df[df['entity_type']=='hotel']):>10,}")
    print(f"  Restaurants:    {len(df[df['entity_type']=='restaurant']):>10,}")
    print(f"  Attractions:    {len(df[df['entity_type']=='attraction']):>10,}")
    print(f"  Stars coverage: {df['stars'].notna().mean():>10.1%}")
    print(f"  Coords coverage:{df['latitude'].notna().mean():>10.1%}")
    print(f"  Avg rating:     {df['stars'].mean():>10.2f}")
    print("=" * 55)

    print("\nTop 20 cities:")
    for city, count in df["city"].value_counts().head(20).items():
        print(f"  {city:<20} {count:>6,}")

    print("\nDone! Files in output/")


if __name__ == "__main__":
    main()
