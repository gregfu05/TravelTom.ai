"""Shared pytest configuration for API tests."""

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# The API settings require a database URL at import time.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://traveltom:traveltom@localhost:5432/traveltom",
)
