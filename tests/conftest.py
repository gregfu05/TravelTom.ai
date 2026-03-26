"""Shared pytest configuration for API tests."""

import os
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# The API settings require a database URL at import time.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://traveltom:traveltom@localhost:5432/traveltom",
)
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("CHAT_RATE_LIMIT", "30/minute")

from app.core.config import get_settings  # noqa: E402
from app.core.security import get_azure_b2c_scheme, get_chat_rate_limiter  # noqa: E402


@pytest.fixture(autouse=True)
def reset_settings_and_rate_limit_state():
    get_settings.cache_clear()
    get_azure_b2c_scheme.cache_clear()
    get_chat_rate_limiter().reset()
    yield
    get_settings.cache_clear()
    get_azure_b2c_scheme.cache_clear()
    get_chat_rate_limiter().reset()
