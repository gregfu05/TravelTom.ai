import warnings
from pathlib import Path

import folium  
import geopandas as gpd  
import matplotlib.pyplot as plt
import numpy as np 
import pandas as pd  
import plotly.express as px
import plotly.graph_objects as go  
import seaborn as sns
from folium.plugins import HeatMap  
from scipy.stats import pearsonr  
from shapely.geometry import Point  
from sklearn.cluster import KMeans 
from sklearn.linear_model import LinearRegression  
from sklearn.preprocessing import StandardScaler 

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
