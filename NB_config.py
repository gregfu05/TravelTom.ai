# noqa: F401 - Imports re-exported for use in notebooks
import warnings
from pathlib import Path

import folium  # noqa: F401
import geopandas as gpd  # noqa: F401
import matplotlib.pyplot as plt
import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401
import plotly.express as px  # noqa: F401
import plotly.graph_objects as go  # noqa: F401
import seaborn as sns
from folium.plugins import HeatMap  # noqa: F401
from scipy.stats import pearsonr  # noqa: F401
from shapely.geometry import Point  # noqa: F401
from sklearn.cluster import KMeans  # noqa: F401
from sklearn.linear_model import LinearRegression  # noqa: F401
from sklearn.preprocessing import StandardScaler  # noqa: F401

warnings.filterwarnings("ignore")

# Set plotting styles
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")
plt.rcParams["figure.figsize"] = (14, 5)

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent

OUTPUT_DIR = ROOT / "traveltom" / "datasets" / "Composite"
RAW_DIR = ROOT / "traveltom" / "datasets" / "Composite"
CACHE_DIR = ROOT / "cache"

DATASET_PATH = OUTPUT_DIR / "traveltom_clean.csv"
CITIES_META_PATH = RAW_DIR / "cities_metadata.csv"


# ── Column Subsets (load only what each notebook needs) ──────────────────────
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
KMEANS_CLUSTERS = 10  # starting point for hotspot detection
KMEANS_SEED = 42

# ── Plotting Defaults ─────────────────────────────────────────────────────────
PLOTLY_TEMPLATE = "plotly_white"  # consistent across all px/go charts
FOLIUM_TILES = "CartoDB positron"
MAP_CENTER = {"lat": 20.0, "lon": 0.0}  # world-centered default
SCATTER_ALPHA = 0.4
FIG_SIZE = (14, 5)
