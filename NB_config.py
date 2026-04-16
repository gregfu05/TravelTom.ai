import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

plt.style.use("seaborn-v0_8")
sns.set_palette("husl")
plt.rcParams["figure.figsize"] = (14, 5)

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent

OUTPUT_DIR = ROOT / "traveltom" / "datasets" / "composite"
RAW_DIR = ROOT / "traveltom" / "datasets" / "composite"
CACHE_DIR = ROOT / "cache"

DATASET_PATH = OUTPUT_DIR / "traveltom_clean2.csv"
CITIES_META_PATH = RAW_DIR / "cities_metadata.csv"


# ── Column Subsets ──────────────────────
GEO_COLS = [
    "business_id",
    "name",
    "city",
    "state",
    "country",
    "country_name",
    "continent",
    "latitude",
    "longitude",
    "entity_type",
]

RATING_COLS = [
    "business_id",
    "name",
    "stars",
    "review_count",
    "popularity",
    "source",
    "entity_type",
    "city",
    "continent",
    "hours",
]

CATEGORY_COLS = [
    "business_id",
    "name",
    "categories",
    "attributes",
    "description",
    "entity_type",
    "price_level",
    "stars",
]

# ── Clustering Config (NB2) ───────────────────────────────────────────────────
KMEANS_CLUSTERS = 10
KMEANS_SEED = 42

# ── Plotting Defaults ─────────────────────────────────────────────────────────
PLOTLY_TEMPLATE = "plotly_white"
FOLIUM_TILES = "CartoDB positron"
MAP_CENTER = {"lat": 20.0, "lon": 0.0}
SCATTER_ALPHA = 0.4
FIG_SIZE = (14, 5)
