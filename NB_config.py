# Core data manipulation and analysis
import pandas as pd
import numpy as np

# Visualization libraries
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go

# Spatial and mapping (for geo notebook)
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from shapely.geometry import Point

# Statistical and ML utilities
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from scipy.stats import pearsonr
from sklearn.preprocessing import StandardScaler

# Utilities
import json
import warnings

warnings.filterwarnings("ignore")

# Set plotting styles
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")

# ── Paths ────────────────────────────────────────────────────────────────────
from pathlib import Path

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

# ── Apply styles (matches your imports) ──────────────────────────────────────
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")
plt.rcParams["figure.figsize"] = FIG_SIZE

# ── Suppress known noisy warnings ────────────────────────────────────────────
import warnings

warnings.filterwarnings("ignore")
