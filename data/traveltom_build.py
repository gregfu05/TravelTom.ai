#!/usr/bin/env python3
"""
TravelTom Super Dataset Builder v3
═══════════════════════════════════
Builds a Yelp-schema-compatible global travel dataset from 11 sources.
No API keys needed except Kaggle.

Output: output/traveltom_full.parquet + .csv
"""

import os, sys, time, json, hashlib, logging, subprocess
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
import requests
from tqdm import tqdm

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
OUTPUT_DIR   = Path("output")
RAW_DIR      = Path("raw_data")
CACHE_DIR    = Path("cache")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_DELAY = 2.5   # be polite to OSM servers
METEO_DELAY   = 0.25

# Unified schema — every row in the final dataset has these columns
SCHEMA = [
    "business_id", "name", "city", "state", "country", "country_name",
    "continent", "latitude", "longitude", "stars", "review_count",
    "categories", "attributes", "hours", "is_open", "address",
    "price_level", "description", "website", "phone", "image_url",
    "source", "entity_type", "popularity",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("build.log")]
)
log = logging.getLogger("tt")

# ═══════════════════════════════════════════════════════════════════════════════
# TARGET CITIES (62 cities, 6 continents)
# Each has a bounding box (south, west, north, east) for Overpass queries
# ═══════════════════════════════════════════════════════════════════════════════
CITIES = {
    # ── Europe (22) ──
    "London":       {"cc":"GB","cont":"Europe","st":"England",       "bb":(51.28,-0.51,51.69,0.33)},
    "Paris":        {"cc":"FR","cont":"Europe","st":"Île-de-France", "bb":(48.81,2.22,48.90,2.47)},
    "Rome":         {"cc":"IT","cont":"Europe","st":"Lazio",         "bb":(41.79,12.37,41.99,12.60)},
    "Barcelona":    {"cc":"ES","cont":"Europe","st":"Catalonia",     "bb":(41.32,2.05,41.47,2.23)},
    "Amsterdam":    {"cc":"NL","cont":"Europe","st":"North Holland", "bb":(52.33,4.77,52.43,4.98)},
    "Prague":       {"cc":"CZ","cont":"Europe","st":"Prague",        "bb":(50.00,14.30,50.14,14.55)},
    "Vienna":       {"cc":"AT","cont":"Europe","st":"Vienna",        "bb":(48.12,16.20,48.32,16.50)},
    "Berlin":       {"cc":"DE","cont":"Europe","st":"Berlin",        "bb":(52.39,13.23,52.62,13.55)},
    "Istanbul":     {"cc":"TR","cont":"Europe","st":"Istanbul",      "bb":(40.88,28.63,41.20,29.35)},
    "Lisbon":       {"cc":"PT","cont":"Europe","st":"Lisbon",        "bb":(38.69,-9.23,38.80,-9.09)},
    "Madrid":       {"cc":"ES","cont":"Europe","st":"Madrid",        "bb":(40.33,-3.83,40.53,-3.58)},
    "Athens":       {"cc":"GR","cont":"Europe","st":"Attica",        "bb":(37.90,23.68,38.05,23.80)},
    "Dublin":       {"cc":"IE","cont":"Europe","st":"Leinster",      "bb":(53.28,-6.39,53.41,-6.11)},
    "Budapest":     {"cc":"HU","cont":"Europe","st":"Budapest",      "bb":(47.43,19.00,47.56,19.15)},
    "Edinburgh":    {"cc":"GB","cont":"Europe","st":"Scotland",      "bb":(55.90,-3.30,55.98,-3.10)},
    "Florence":     {"cc":"IT","cont":"Europe","st":"Tuscany",       "bb":(43.74,11.20,43.80,11.30)},
    "Munich":       {"cc":"DE","cont":"Europe","st":"Bavaria",       "bb":(48.06,11.45,48.22,11.68)},
    "Copenhagen":   {"cc":"DK","cont":"Europe","st":"Capital Region","bb":(55.63,12.47,55.73,12.63)},
    "Stockholm":    {"cc":"SE","cont":"Europe","st":"Stockholm",     "bb":(59.28,17.94,59.40,18.16)},
    "Milan":        {"cc":"IT","cont":"Europe","st":"Lombardy",      "bb":(45.40,9.10,45.52,9.28)},
    "Porto":        {"cc":"PT","cont":"Europe","st":"Porto",         "bb":(41.12,-8.68,41.19,-8.57)},
    "Seville":      {"cc":"ES","cont":"Europe","st":"Andalusia",     "bb":(37.33,-6.02,37.42,-5.90)},
    # ── Asia (17) ──
    "Tokyo":        {"cc":"JP","cont":"Asia","st":"Tokyo",           "bb":(35.55,139.55,35.82,139.90)},
    "Bangkok":      {"cc":"TH","cont":"Asia","st":"Bangkok",         "bb":(13.60,100.35,13.95,100.75)},
    "Singapore":    {"cc":"SG","cont":"Asia","st":"Singapore",       "bb":(1.22,103.60,1.47,104.00)},
    "Hong Kong":    {"cc":"HK","cont":"Asia","st":"Hong Kong",       "bb":(22.15,113.83,22.56,114.35)},
    "Seoul":        {"cc":"KR","cont":"Asia","st":"Seoul",           "bb":(37.42,126.80,37.70,127.15)},
    "Kuala Lumpur": {"cc":"MY","cont":"Asia","st":"KL",              "bb":(3.05,101.60,3.20,101.78)},
    "Bali":         {"cc":"ID","cont":"Asia","st":"Bali",            "bb":(-8.85,114.43,-8.06,115.71)},
    "Delhi":        {"cc":"IN","cont":"Asia","st":"Delhi",           "bb":(28.40,76.84,28.88,77.35)},
    "Mumbai":       {"cc":"IN","cont":"Asia","st":"Maharashtra",     "bb":(18.89,72.77,19.27,72.98)},
    "Kyoto":        {"cc":"JP","cont":"Asia","st":"Kyoto",           "bb":(34.93,135.70,35.08,135.82)},
    "Shanghai":     {"cc":"CN","cont":"Asia","st":"Shanghai",        "bb":(31.00,121.20,31.40,121.80)},
    "Beijing":      {"cc":"CN","cont":"Asia","st":"Beijing",         "bb":(39.75,116.20,40.02,116.55)},
    "Hanoi":        {"cc":"VN","cont":"Asia","st":"Hanoi",           "bb":(20.98,105.75,21.08,105.88)},
    "Taipei":       {"cc":"TW","cont":"Asia","st":"Taipei",          "bb":(24.96,121.45,25.11,121.61)},
    "Chiang Mai":   {"cc":"TH","cont":"Asia","st":"Chiang Mai",      "bb":(18.74,98.94,18.82,99.02)},
    "Dubai":        {"cc":"AE","cont":"Asia","st":"Dubai",           "bb":(25.05,55.10,25.35,55.40)},
    "Amman":        {"cc":"JO","cont":"Asia","st":"Amman",           "bb":(31.90,35.85,31.99,35.98)},
    # ── Americas (14) ──
    "New York":     {"cc":"US","cont":"North America","st":"NY",     "bb":(40.49,-74.26,40.92,-73.70)},
    "Los Angeles":  {"cc":"US","cont":"North America","st":"CA",     "bb":(33.70,-118.67,34.34,-118.15)},
    "San Francisco":{"cc":"US","cont":"North America","st":"CA",     "bb":(37.70,-122.52,37.83,-122.35)},
    "Miami":        {"cc":"US","cont":"North America","st":"FL",     "bb":(25.70,-80.30,25.86,-80.13)},
    "Mexico City":  {"cc":"MX","cont":"North America","st":"CDMX",   "bb":(19.28,-99.25,19.50,-99.05)},
    "Cancun":       {"cc":"MX","cont":"North America","st":"Q.Roo",  "bb":(21.05,-86.88,21.20,-86.74)},
    "Toronto":      {"cc":"CA","cont":"North America","st":"ON",     "bb":(43.58,-79.64,43.86,-79.12)},
    "Vancouver":    {"cc":"CA","cont":"North America","st":"BC",     "bb":(49.20,-123.27,49.32,-123.02)},
    "Buenos Aires": {"cc":"AR","cont":"South America","st":"CABA",   "bb":(-34.70,-58.53,-34.53,-58.33)},
    "Rio de Janeiro":{"cc":"BR","cont":"South America","st":"RJ",    "bb":(-23.08,-43.48,-22.85,-43.17)},
    "Lima":         {"cc":"PE","cont":"South America","st":"Lima",   "bb":(-12.20,-77.15,-12.00,-76.90)},
    "Bogota":       {"cc":"CO","cont":"South America","st":"Bogota", "bb":(4.52,-74.20,4.80,-74.00)},
    "Cusco":        {"cc":"PE","cont":"South America","st":"Cusco",  "bb":(-13.55,-72.00,-13.49,-71.94)},
    "Havana":       {"cc":"CU","cont":"North America","st":"Havana", "bb":(23.08,-82.45,23.17,-82.33)},
    # ── Africa (5) ──
    "Cape Town":    {"cc":"ZA","cont":"Africa","st":"W. Cape",       "bb":(-34.15,18.35,-33.85,18.70)},
    "Cairo":        {"cc":"EG","cont":"Africa","st":"Cairo",         "bb":(29.95,31.17,30.13,31.40)},
    "Nairobi":      {"cc":"KE","cont":"Africa","st":"Nairobi",       "bb":(-1.37,36.70,-1.18,36.92)},
    "Marrakech":    {"cc":"MA","cont":"Africa","st":"Marrakech",     "bb":(31.58,-8.05,31.67,-7.95)},
    "Johannesburg": {"cc":"ZA","cont":"Africa","st":"Gauteng",       "bb":(-26.33,27.92,-26.10,28.15)},
    # ── Oceania (3) ──
    "Sydney":       {"cc":"AU","cont":"Oceania","st":"NSW",          "bb":(-33.95,151.05,-33.75,151.30)},
    "Melbourne":    {"cc":"AU","cont":"Oceania","st":"VIC",          "bb":(-37.87,144.89,-37.74,145.05)},
    "Auckland":     {"cc":"NZ","cont":"Oceania","st":"Auckland",     "bb":(-36.94,174.70,-36.82,174.85)},
}

KAGGLE_DATASETS = [
    "cosmox23/popular-tourist-destinations-and-their-features",
    "raj713335/tbo-hotels-dataset",
    "juanmah/world-cities",
    "ramjasmaurya/global-tourist-attractions",
    "koki25ando/european-cities-tourist-information",
    "inigolopezrioboo/a-tripadvisor-dataset-for-nlp-tasks",
    "ngshiheng/michelin-guide-restaurants-2021",
    "shaistashahid/world-famous-places",
]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def setup():
    for d in [OUTPUT_DIR, RAW_DIR, CACHE_DIR]:
        d.mkdir(exist_ok=True)


def make_id(name: str, lat, lon) -> str:
    """Generate a deterministic business_id from name + coords."""
    raw = f"{str(name).lower().strip()}|{lat}|{lon}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def cached_get(key: str, url: str, params=None, delay=0, timeout=30):
    h = hashlib.sha256(key.encode()).hexdigest()
    fp = CACHE_DIR / f"{h}.json"
    if fp.exists():
        return json.loads(fp.read_text())
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        fp.write_text(json.dumps(data))
        if delay: time.sleep(delay)
        return data
    except Exception as e:
        log.warning(f"  GET failed [req={h[:8]}] ({type(e).__name__})")
        return None


def cached_post(key: str, url: str, data_body: str, delay=0, timeout=90):
    h = hashlib.md5(key.encode()).hexdigest()
    fp = CACHE_DIR / f"{h}.json"
    if fp.exists():
        return json.loads(fp.read_text())
    try:
        r = requests.post(url, data={"data": data_body}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        fp.write_text(json.dumps(data))
        if delay: time.sleep(delay)
        return data
    except Exception as e:
        log.warning(f"  POST failed [req={h[:8]}] ({type(e).__name__})")
        return None


def to_unified(rows: list[dict]) -> pd.DataFrame:
    """Convert list of dicts to DataFrame with unified schema."""
    df = pd.DataFrame(rows)
    for col in SCHEMA:
        if col not in df.columns:
            df[col] = np.nan
    return df[SCHEMA]


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1: DOWNLOAD KAGGLE DATASETS
# ═══════════════════════════════════════════════════════════════════════════════
def stage_download():
    log.info("━" * 60)
    log.info("STAGE 1 │ Downloading Kaggle datasets")
    log.info("━" * 60)

    # Use Kaggle Python API directly (bypasses .exe blocking on Windows)
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
    except Exception as e:
        log.error(f"  Kaggle auth failed: {e}")
        log.error("  Set env vars: KAGGLE_USERNAME and KAGGLE_KEY")
        log.error("  Or place kaggle.json in ~/.kaggle/")
        sys.exit(1)

    for slug in KAGGLE_DATASETS:
        d = RAW_DIR / slug.replace("/", "__")
        if d.exists() and any(d.glob("*.csv")):
            log.info(f"  [cached] {slug}")
            continue
        d.mkdir(parents=True, exist_ok=True)
        log.info(f"  ↓ {slug}")
        try:
            api.dataset_download_files(slug, path=str(d), unzip=True)
            csvs = list(d.glob("*.csv"))
            total = sum(sum(1 for _ in open(f, encoding="utf-8", errors="ignore")) - 1 for f in csvs)
            log.info(f"    OK → {len(csvs)} files, ~{total:,} rows")
        except Exception as e:
            log.warning(f"    FAIL: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 2: EXTRACT & NORMALIZE KAGGLE DATA
# ═══════════════════════════════════════════════════════════════════════════════
def read_dir(slug: str) -> pd.DataFrame:
    d = RAW_DIR / slug.replace("/", "__")
    frames = []
    for f in d.glob("*.csv"):
        try:
            df = pd.read_csv(f, low_memory=False, on_bad_lines="skip")
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            frames.append(df)
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(f, low_memory=False, on_bad_lines="skip", encoding="latin-1")
                df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
                frames.append(df)
            except: pass
        except: pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def norm_tbo_hotels() -> list[dict]:
    """Normalize TBO Hotels (1M+ rows) to unified schema."""
    log.info("  Processing TBO Hotels (this takes a few minutes for 1M+ rows)...")
    d = RAW_DIR / "raj713335__tbo-hotels-dataset"
    all_chunks = []
    for f in d.glob("*.csv"):
        try:
            for chunk in pd.read_csv(f, chunksize=100_000, low_memory=False,
                                      on_bad_lines="skip", encoding="latin-1"):
                chunk.columns = [c.strip().lower().replace(" ", "_") for c in chunk.columns]

                # Parse lat/lng from "map" column (format: "lat|lng" or similar)
                if "map" in chunk.columns:
                    map_split = chunk["map"].astype(str).str.split("|", expand=True)
                    if map_split.shape[1] >= 2:
                        chunk["_lat"] = pd.to_numeric(map_split[0], errors="coerce")
                        chunk["_lng"] = pd.to_numeric(map_split[1], errors="coerce")
                    else:
                        chunk["_lat"] = np.nan
                        chunk["_lng"] = np.nan
                else:
                    chunk["_lat"] = np.nan
                    chunk["_lng"] = np.nan

                # Vectorized extraction — no iterrows
                sub = pd.DataFrame({
                    "name": chunk.get("hotelname", pd.Series(dtype=str)).astype(str).str.strip(),
                    "city": chunk.get("cityname", pd.Series(dtype=str)).astype(str).str.strip(),
                    "country": chunk.get("countycode", chunk.get("countrycode", pd.Series(dtype=str))).astype(str).str.strip(),
                    "country_name": chunk.get("countyname", chunk.get("countryname", pd.Series(dtype=str))).astype(str).str.strip(),
                    "latitude": chunk["_lat"],
                    "longitude": chunk["_lng"],
                    "stars": pd.to_numeric(chunk.get("hotelrating", pd.Series(dtype=float)), errors="coerce"),
                    "review_count": 0,
                    "categories": "hotel;lodging",
                    "address": chunk.get("address", pd.Series(dtype=str)).astype(str).str.strip().str[:500],
                    "description": chunk.get("description", pd.Series(dtype=str)).astype(str).str.strip().str[:1000],
                    "phone": chunk.get("phonenumber", pd.Series(dtype=str)).astype(str).str.strip(),
                    "website": chunk.get("hotelwebsiteurl", pd.Series(dtype=str)).astype(str).str.strip(),
                    "source": "tbo_hotels",
                    "entity_type": "hotel",
                    "is_open": 1,
                })
                # Drop rows with no name
                sub = sub[sub["name"].notna() & (sub["name"] != "") & (sub["name"] != "nan")]
                all_chunks.append(sub)
                log.info(f"    chunk: {len(sub):,} hotels")
        except Exception as e:
            log.warning(f"    Error in {f.name}: {e}")

    if all_chunks:
        result = pd.concat(all_chunks, ignore_index=True)
        log.info(f"    -> {len(result):,} hotels total")
        return result.to_dict("records")
    return []


def norm_michelin() -> list[dict]:
    """Normalize Michelin Guide restaurants."""
    log.info("  Processing Michelin Guide...")
    df = read_dir("ngshiheng/michelin-guide-restaurants-2021")
    if df.empty: return []
    rows = []
    for _, r in df.iterrows():
        name = r.get("name", "")
        if not name or pd.isna(name): continue

        # Parse location (format: "City, Region, Country")
        loc = str(r.get("location", ""))
        parts = [p.strip() for p in loc.split(",")]
        city = parts[0] if parts else ""

        lat = r.get("latitude") or r.get("lat")
        lon = r.get("longitude") or r.get("lon") or r.get("lng")
        cuisine = r.get("cuisine", "")
        price = r.get("price", "")

        # Convert Michelin stars/awards to 1-5 scale
        award = str(r.get("award", "")).lower()
        if "3 star" in award:    stars = 5.0
        elif "2 star" in award:  stars = 4.8
        elif "1 star" in award:  stars = 4.5
        elif "bib" in award:     stars = 4.2
        else:                    stars = 4.0  # selected = good

        price_level = len(str(price)) if price and not pd.isna(price) else np.nan

        cats = ["restaurant"]
        if cuisine and not pd.isna(cuisine):
            cats.append(str(cuisine).lower().strip())

        rows.append({
            "name": str(name).strip(),
            "city": city,
            "latitude": float(lat) if lat and not pd.isna(lat) else np.nan,
            "longitude": float(lon) if lon and not pd.isna(lon) else np.nan,
            "stars": stars,
            "review_count": 50,  # Michelin-rated = established
            "categories": ";".join(cats),
            "price_level": price_level,
            "website": str(r.get("url", "")) if not pd.isna(r.get("url", np.nan)) else "",
            "source": "michelin",
            "entity_type": "restaurant",
            "is_open": 1,
        })
    log.info(f"    → {len(rows):,} restaurants")
    return rows


def norm_tripadvisor() -> list[dict]:
    """Normalize TripAdvisor 6-city restaurant dataset."""
    log.info("  Processing TripAdvisor restaurants...")
    df = read_dir("inigolopezrioboo/a-tripadvisor-dataset-for-nlp-tasks")
    if df.empty: return []
    rows = []
    for _, r in df.iterrows():
        name = r.get("restaurant_name") or r.get("name") or r.get("restaurantname", "")
        if not name or pd.isna(name): continue

        rating = r.get("rating") or r.get("avg_rating") or r.get("stars")
        reviews = r.get("total_reviews") or r.get("review_count") or r.get("num_reviews", 0)
        city = r.get("city", "")
        cuisine = r.get("cuisine") or r.get("cuisine_type", "")

        cats = ["restaurant"]
        if cuisine and not pd.isna(cuisine):
            cats.append(str(cuisine).lower().strip())

        rows.append({
            "name": str(name).strip(),
            "city": str(city).strip() if city and not pd.isna(city) else "",
            "stars": float(rating) if rating and not pd.isna(rating) else np.nan,
            "review_count": int(float(reviews)) if reviews and not pd.isna(reviews) else 0,
            "categories": ";".join(cats),
            "source": "tripadvisor",
            "entity_type": "restaurant",
            "is_open": 1,
        })
    log.info(f"    → {len(rows):,} restaurants")
    return rows


def norm_destinations() -> list[dict]:
    """Normalize Popular Tourist Destinations."""
    log.info("  Processing Popular Tourist Destinations...")
    df = read_dir("cosmox23/popular-tourist-destinations-and-their-features")
    if df.empty: return []
    log.info(f"    Columns found: {list(df.columns)}")
    rows = []
    for _, r in df.iterrows():
        # Actual cols: destination_name, country, continent, type, avg_cost_(usd/day),
        # best_season, avg_rating, annual_visitors_(m), unesco_site
        name = r.get("destination_name") or r.get("destination") or r.get("name", "")
        if not name or pd.isna(name): continue

        cat = str(r.get("type") or r.get("category", "")).lower() if not pd.isna(r.get("type", r.get("category", np.nan))) else "attraction"
        country = r.get("country", "")
        cont = r.get("continent", "")
        rating = r.get("avg_rating") or r.get("rating") or r.get("stars")
        visitors = r.get("annual_visitors_(m)") or r.get("annual_visitors") or r.get("visitors", 0)
        cost = r.get("avg_cost_(usd/day)") or r.get("avg_cost_($)") or r.get("avg_cost") or r.get("cost")
        season = r.get("best_season") or r.get("season", "")

        etype = "attraction"
        if cat in ["beach", "nature", "adventure"]: etype = "activity"
        elif cat in ["city"]: etype = "attraction"

        attrs = {}
        if cost and not pd.isna(cost): attrs["avg_cost_usd"] = float(cost)
        if season and not pd.isna(season): attrs["best_season"] = str(season)
        unesco = r.get("unesco_site") or r.get("unesco", "")
        if unesco and not pd.isna(unesco): attrs["unesco"] = str(unesco)

        rows.append({
            "name": str(name).strip(),
            "country_name": str(country).strip() if country and not pd.isna(country) else "",
            "continent": str(cont).strip() if cont and not pd.isna(cont) else "",
            "stars": float(rating) if rating and not pd.isna(rating) else np.nan,
            "review_count": int(float(visitors)) if visitors and not pd.isna(visitors) else 0,
            "categories": f"attraction;{cat}",
            "attributes": json.dumps(attrs) if attrs else "",
            "source": "kaggle_destinations",
            "entity_type": etype,
            "is_open": 1,
        })
    log.info(f"    -> {len(rows):,} destinations")
    return rows


def norm_global_attractions() -> list[dict]:
    """Normalize Global Tourist Attractions + World Famous Places."""
    log.info("  Processing Global Attractions + Famous Places...")
    rows = []
    for slug, tag in [
        ("ramjasmaurya/global-tourist-attractions", "kaggle_global"),
        ("shaistashahid/world-famous-places", "kaggle_famous"),
        ("koki25ando/european-cities-tourist-information", "kaggle_european"),
    ]:
        df = read_dir(slug)
        if df.empty: continue
        for _, r in df.iterrows():
            name = r.get("name") or r.get("attraction") or r.get("place", "")
            if not name or pd.isna(name): continue

            lat = r.get("latitude") or r.get("lat")
            lon = r.get("longitude") or r.get("lon") or r.get("lng")
            city = r.get("city", "")
            country = r.get("country", "")
            rating = r.get("rating") or r.get("stars") or r.get("avg_rating")
            reviews = r.get("review_count") or r.get("reviews") or r.get("num_reviews", 0)
            desc = r.get("description", "")
            cat = r.get("category") or r.get("type", "attraction")

            rows.append({
                "name": str(name).strip(),
                "city": str(city).strip() if city and not pd.isna(city) else "",
                "country_name": str(country).strip() if country and not pd.isna(country) else "",
                "latitude": float(lat) if lat and not pd.isna(lat) else np.nan,
                "longitude": float(lon) if lon and not pd.isna(lon) else np.nan,
                "stars": float(rating) if rating and not pd.isna(rating) else np.nan,
                "review_count": int(float(reviews)) if reviews and not pd.isna(reviews) else 0,
                "categories": f"attraction;{str(cat).lower().strip()}" if cat and not pd.isna(cat) else "attraction",
                "description": str(desc).strip()[:1000] if desc and not pd.isna(desc) else "",
                "source": tag,
                "entity_type": "attraction",
                "is_open": 1,
            })
    log.info(f"    → {len(rows):,} attractions")
    return rows


def stage_kaggle() -> pd.DataFrame:
    log.info("━" * 60)
    log.info("STAGE 2 │ Extracting & normalizing Kaggle data")
    log.info("━" * 60)

    all_rows = []
    all_rows.extend(norm_tbo_hotels())
    all_rows.extend(norm_michelin())
    all_rows.extend(norm_tripadvisor())
    all_rows.extend(norm_destinations())
    all_rows.extend(norm_global_attractions())

    df = to_unified(all_rows)
    log.info(f"  Total Kaggle rows: {len(df):,}")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3: OPENSTREETMAP VIA OVERPASS
# ═══════════════════════════════════════════════════════════════════════════════
OVERPASS_QUERIES = {
    "attraction": """
        [out:json][timeout:60];
        (
          nwr["tourism"="attraction"]["name"]({bb});
          nwr["tourism"="museum"]["name"]({bb});
          nwr["tourism"="viewpoint"]["name"]({bb});
          nwr["historic"]["name"]({bb});
          nwr["tourism"="artwork"]["name"]({bb});
          nwr["leisure"="park"]["name"]["tourism"]({bb});
        );
        out center body 300;
    """,
    "restaurant": """
        [out:json][timeout:60];
        (
          nwr["amenity"="restaurant"]["name"]({bb});
          nwr["amenity"="cafe"]["name"]["cuisine"]({bb});
          nwr["amenity"="bar"]["name"]["cuisine"]({bb});
        );
        out center body 500;
    """,
    "hotel": """
        [out:json][timeout:60];
        (
          nwr["tourism"="hotel"]["name"]({bb});
          nwr["tourism"="hostel"]["name"]({bb});
          nwr["tourism"="guest_house"]["name"]({bb});
        );
        out center body 300;
    """,
}


def parse_osm_element(el: dict, city: str, meta: dict, etype: str) -> dict:
    """Convert one OSM element to unified row."""
    tags = el.get("tags", {})
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    name = tags.get("name", "")
    if not name: return None

    # Build categories from tags
    cats = [etype]
    for key in ["tourism", "historic", "leisure", "amenity", "cuisine", "shop"]:
        v = tags.get(key)
        if v and v != "yes":
            cats.append(v.replace(";", ",").lower())

    # Build attributes JSON
    attrs = {}
    for key in ["wheelchair", "internet_access", "smoking", "outdoor_seating",
                 "takeaway", "delivery", "diet:vegetarian", "diet:vegan",
                 "air_conditioning", "capacity", "fee"]:
        v = tags.get(key)
        if v: attrs[key.replace(":", "_")] = v

    # Build hours JSON
    hours_raw = tags.get("opening_hours", "")
    hours = hours_raw if hours_raw else ""

    # Stars from OSM (rare but exists)
    osm_stars = tags.get("stars")
    stars = float(osm_stars) if osm_stars and osm_stars.replace(".", "").isdigit() else np.nan

    return {
        "name": name.strip(),
        "city": city,
        "state": meta["st"],
        "country": meta["cc"],
        "continent": meta["cont"],
        "latitude": float(lat) if lat else np.nan,
        "longitude": float(lon) if lon else np.nan,
        "stars": stars,
        "review_count": 0,
        "categories": ";".join(cats),
        "attributes": json.dumps(attrs) if attrs else "",
        "hours": hours,
        "is_open": 1,
        "address": tags.get("addr:street", ""),
        "website": tags.get("website", ""),
        "phone": tags.get("phone", ""),
        "description": tags.get("description", ""),
        "source": "openstreetmap",
        "entity_type": etype,
    }


def stage_osm() -> pd.DataFrame:
    log.info("━" * 60)
    log.info("STAGE 3 │ Querying OpenStreetMap (Overpass API)")
    log.info(f"         {len(CITIES)} cities × 3 types = {len(CITIES)*3} queries")
    log.info("━" * 60)

    all_rows = []
    for city, meta in tqdm(CITIES.items(), desc="  Cities"):
        bb = meta["bb"]
        bb_str = f"{bb[0]},{bb[1]},{bb[2]},{bb[3]}"

        for etype, query_template in OVERPASS_QUERIES.items():
            query = query_template.replace("{bb}", bb_str)
            cache_key = f"osm_{city}_{etype}"
            data = cached_post(cache_key, OVERPASS_URL, query, delay=OVERPASS_DELAY)

            if not data or "elements" not in data:
                continue

            count = 0
            for el in data["elements"]:
                row = parse_osm_element(el, city, meta, etype)
                if row:
                    all_rows.append(row)
                    count += 1

        # Log per city (don't spam — just summary)

    df = to_unified(all_rows)
    log.info(f"  Total OSM rows: {len(df):,}")

    # Per-city summary
    if len(df) > 0:
        summary = df.groupby("city")["entity_type"].value_counts().unstack(fill_value=0)
        log.info(f"\n{summary.to_string()}\n")

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 4: BUILD CITIES METADATA
# ═══════════════════════════════════════════════════════════════════════════════
def stage_cities_meta() -> pd.DataFrame:
    log.info("━" * 60)
    log.info("STAGE 4 │ Building cities metadata")
    log.info("━" * 60)

    rows = []
    for city, meta in CITIES.items():
        s, w, n, e = meta["bb"]
        rows.append({
            "city": city,
            "country_code": meta["cc"],
            "continent": meta["cont"],
            "state": meta["st"],
            "latitude": round((s + n) / 2, 4),
            "longitude": round((w + e) / 2, 4),
        })
    df = pd.DataFrame(rows)

    # REST Countries
    log.info("  Fetching country metadata...")
    try:
        data = requests.get("https://restcountries.com/v3.1/all", timeout=30).json()
        cmap = {}
        for c in data:
            code = c.get("cca2", "")
            if not code: continue
            curr = c.get("currencies", {})
            ck = list(curr.keys())[0] if curr else None
            cmap[code] = {
                "country_name": c["name"]["common"],
                "currency": ck,
                "languages": ", ".join(c.get("languages", {}).values()),
            }
        enrich = pd.DataFrame.from_dict(cmap, orient="index").reset_index().rename(columns={"index": "country_code"})
        df = df.merge(enrich, on="country_code", how="left")
    except Exception as e:
        log.warning(f"  REST Countries failed: {e}")

    # Open-Meteo climate
    log.info("  Fetching climate data...")
    jan_t, jul_t, rain = [], [], []
    for _, r in tqdm(df.iterrows(), total=len(df), desc="  Climate"):
        d = cached_get(
            f"meteo_{r['latitude']}_{r['longitude']}",
            "https://archive-api.open-meteo.com/v1/archive",
            params={"latitude": r["latitude"], "longitude": r["longitude"],
                    "start_date": "2023-01-01", "end_date": "2023-12-31",
                    "daily": "temperature_2m_mean,precipitation_sum", "timezone": "auto"},
            delay=METEO_DELAY
        )
        try:
            temps = d["daily"]["temperature_2m_mean"]
            prcp = d["daily"]["precipitation_sum"]
            jv = [t for t in temps[0:31] if t is not None]
            jlv = [t for t in temps[181:212] if t is not None]
            jan_t.append(round(sum(jv)/len(jv), 1) if jv else None)
            jul_t.append(round(sum(jlv)/len(jlv), 1) if jlv else None)
            rain.append(round(sum(p for p in prcp if p), 0))
        except:
            jan_t.append(None); jul_t.append(None); rain.append(None)

    df["avg_temp_jan_c"] = jan_t
    df["avg_temp_jul_c"] = jul_t
    df["annual_rainfall_mm"] = rain

    # Population from world-cities
    log.info("  Merging population data...")
    wc = read_dir("juanmah/world-cities")
    if len(wc) > 0:
        name_col = next((c for c in wc.columns if c in ["city", "name", "city_ascii"]), None)
        pop_col = next((c for c in wc.columns if "pop" in c.lower()), None)
        if name_col and pop_col:
            wc["_k"] = wc[name_col].str.lower().str.strip()
            wc[pop_col] = pd.to_numeric(wc[pop_col], errors="coerce")
            lookup = dict(wc.sort_values(pop_col, ascending=False).drop_duplicates("_k")[["_k", pop_col]].values)
            df["population"] = df["city"].str.lower().map(lookup)

    log.info(f"  Cities metadata: {len(df)} rows")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 5: MERGE, DEDUPLICATE, COMPUTE FEATURES
# ═══════════════════════════════════════════════════════════════════════════════
def stage_merge(kaggle_df: pd.DataFrame, osm_df: pd.DataFrame) -> pd.DataFrame:
    log.info("━" * 60)
    log.info("STAGE 5 │ Merging & deduplicating")
    log.info("━" * 60)

    df = pd.concat([kaggle_df, osm_df], ignore_index=True)
    log.info(f"  Combined: {len(df):,} rows")

    # ── Generate business_id ──
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["business_id"] = df.apply(
        lambda r: make_id(r["name"], r["latitude"], r["longitude"]), axis=1
    )

    # ── Deduplicate ──
    # Priority: michelin > tripadvisor > openstreetmap > kaggle_* > tbo_hotels
    source_priority = {
        "michelin": 0, "tripadvisor": 1, "openstreetmap": 2,
        "kaggle_destinations": 3, "kaggle_global": 4, "kaggle_famous": 5,
        "kaggle_european": 6, "tbo_hotels": 7,
    }
    df["_priority"] = df["source"].map(source_priority).fillna(9)

    before = len(df)

    # Method 1: exact business_id dedup (same name + same ~coords)
    df = df.sort_values("_priority").drop_duplicates("business_id", keep="first")
    log.info(f"  After ID dedup: {before:,} → {len(df):,}")

    # Method 2: name + rounded coords for near-duplicates
    df["_name_key"] = df["name"].str.lower().str.strip()
    has_coords = df["latitude"].notna() & df["longitude"].notna()
    df_c = df[has_coords].copy()
    df_nc = df[~has_coords].copy()

    if len(df_c) > 0:
        df_c["_lr"] = (df_c["latitude"] * 100).round() / 100
        df_c["_lnr"] = (df_c["longitude"] * 100).round() / 100
        before2 = len(df_c)
        df_c = df_c.sort_values("_priority").drop_duplicates(["_name_key", "_lr", "_lnr"], keep="first")
        df_c = df_c.drop(columns=["_lr", "_lnr"])
        log.info(f"  After geo dedup: {before2:,} → {len(df_c):,}")

    df = pd.concat([df_c, df_nc], ignore_index=True)
    df = df.drop(columns=["_priority", "_name_key"], errors="ignore")

    # ── Fill city/country from our cities config where missing ──
    city_lookup = {}
    for city, meta in CITIES.items():
        city_lookup[city.lower()] = meta

    def enrich_geo(row):
        c = str(row.get("city", "")).strip()
        meta = city_lookup.get(c.lower())
        if meta:
            if pd.isna(row.get("country")) or not row.get("country"):
                row["country"] = meta["cc"]
            if pd.isna(row.get("continent")) or not row.get("continent"):
                row["continent"] = meta["cont"]
            if pd.isna(row.get("state")) or not row.get("state"):
                row["state"] = meta["st"]
        return row

    df = df.apply(enrich_geo, axis=1)

    # ── Normalize stars to 1-5 ──
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    df.loc[df["stars"] > 5, "stars"] = 5.0
    df.loc[df["stars"] < 1, "stars"] = np.nan

    # Fill missing stars with median per source
    for src in df["source"].unique():
        mask = (df["source"] == src) & df["stars"].isna()
        median = df.loc[df["source"] == src, "stars"].median()
        if not pd.isna(median):
            df.loc[mask, "stars"] = median

    # ── review_count ──
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0).astype(int)

    # ── popularity score (Kareem's formula) ──
    df["popularity"] = df["stars"] * np.log1p(df["review_count"])

    # ── Regenerate IDs (after dedup) ──
    df["business_id"] = df.apply(
        lambda r: make_id(r["name"], r["latitude"], r["longitude"]), axis=1
    )

    log.info(f"  Final dataset: {len(df):,} rows")
    log.info(f"  Sources: {df['source'].value_counts().to_dict()}")
    log.info(f"  Entity types: {df['entity_type'].value_counts().to_dict()}")
    log.info(f"  Cities with data: {df['city'].nunique()}")
    log.info(f"  Stars coverage: {df['stars'].notna().mean():.1%}")
    log.info(f"  Coords coverage: {df['latitude'].notna().mean():.1%}")

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 6: EXPORT
# ═══════════════════════════════════════════════════════════════════════════════
def stage_export(df: pd.DataFrame, cities_df: pd.DataFrame):
    log.info("━" * 60)
    log.info("STAGE 6 │ Exporting")
    log.info("━" * 60)

    # Main dataset
    pq_path = OUTPUT_DIR / "traveltom_full.parquet"
    df.to_parquet(pq_path, compression="zstd", index=False)
    log.info(f"  ✓ {pq_path} ({pq_path.stat().st_size / 1024 / 1024:.1f} MB)")

    csv_path = OUTPUT_DIR / "traveltom_full.csv"
    df.to_csv(csv_path, index=False)
    log.info(f"  ✓ {csv_path} ({csv_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Cities metadata
    cities_path = OUTPUT_DIR / "cities_metadata.csv"
    cities_df.to_csv(cities_path, index=False)
    log.info(f"  ✓ {cities_path}")

    # Stats
    stats = {
        "total_rows": len(df),
        "unique_cities": int(df["city"].nunique()),
        "unique_countries": int(df["country"].nunique()),
        "by_source": df["source"].value_counts().to_dict(),
        "by_entity_type": df["entity_type"].value_counts().to_dict(),
        "by_continent": df["continent"].value_counts().to_dict() if "continent" in df.columns else {},
        "stars_coverage": f"{df['stars'].notna().mean():.1%}",
        "coords_coverage": f"{df['latitude'].notna().mean():.1%}",
        "top_cities": df["city"].value_counts().head(20).to_dict(),
    }
    stats_path = OUTPUT_DIR / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2, default=str))
    log.info(f"  ✓ {stats_path}")

    # Print summary
    log.info("\n" + "═" * 60)
    log.info("  DATASET SUMMARY")
    log.info("═" * 60)
    log.info(f"  Total rows:      {len(df):>12,}")
    log.info(f"  Unique cities:   {df['city'].nunique():>12,}")
    log.info(f"  Hotels:          {len(df[df['entity_type']=='hotel']):>12,}")
    log.info(f"  Restaurants:     {len(df[df['entity_type']=='restaurant']):>12,}")
    log.info(f"  Attractions:     {len(df[df['entity_type']=='attraction']):>12,}")
    log.info(f"  Activities:      {len(df[df['entity_type']=='activity']):>12,}")
    log.info(f"  With ratings:    {df['stars'].notna().sum():>12,}")
    log.info(f"  With coords:     {df['latitude'].notna().sum():>12,}")
    log.info("═" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    log.info("═" * 60)
    log.info("  TravelTom Super Dataset Builder v3")
    log.info("  Yelp-compatible schema │ 62 cities │ 11 sources")
    log.info("═" * 60)

    setup()

    stage_download()                         # 1. Kaggle
    kaggle_df  = stage_kaggle()              # 2. Normalize Kaggle
    osm_df     = stage_osm()                 # 3. OpenStreetMap
    cities_df  = stage_cities_meta()         # 4. City metadata
    merged_df  = stage_merge(kaggle_df, osm_df)  # 5. Merge + dedup
    stage_export(merged_df, cities_df)       # 6. Export

    log.info("\n  DONE. Check output/ folder.\n")


if __name__ == "__main__":
    main()
