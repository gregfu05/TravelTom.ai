"""Shared pytest configuration for API tests."""

import os
import shutil
import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# The API settings require a database URL at import time.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://traveltom:traveltom@localhost:5432/traveltom",
)
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("CHAT_RATE_LIMIT", "30/minute")
os.environ.setdefault("RECOMMENDER_PRELOAD_ON_STARTUP", "false")

from app.core.config import get_settings  # noqa: E402
from app.core.security import get_azure_b2c_scheme, get_chat_rate_limiter  # noqa: E402

_CUSTOM_TMP_ROOT = Path(
    os.environ.get(
        "TRAVELTOM_TEST_TMP_ROOT",
        str(Path.home() / ".codex" / "memories" / "traveltom-test-tmp"),
    )
)


@pytest.fixture(autouse=True)
def reset_settings_and_rate_limit_state():
    get_settings.cache_clear()
    get_azure_b2c_scheme.cache_clear()
    get_chat_rate_limiter().reset()
    yield
    get_settings.cache_clear()
    get_azure_b2c_scheme.cache_clear()
    get_chat_rate_limiter().reset()


@pytest.fixture
def tmp_path() -> Generator[Path, None, None]:
    """Provide a repo-safe temporary directory independent of pytest basetemp."""

    _CUSTOM_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _CUSTOM_TMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    yield path
    shutil.rmtree(path, ignore_errors=True)
