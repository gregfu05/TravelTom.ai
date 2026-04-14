"""FastAPI application entrypoint."""

# ruff: noqa: E402

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure local repo packages (e.g. `traveltom`) are imported before site-packages.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.telemetry import configure_telemetry
from app.services.recommendation_runtime import preload_recommendation_catalog


@asynccontextmanager
async def app_lifespan(_application: FastAPI):
    """Preload deterministic runtime artifacts before serving requests."""

    settings = get_settings()
    if settings.recommender_preload_on_startup:
        await asyncio.to_thread(preload_recommendation_catalog, settings)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(
        service_name=settings.telemetry_service_name,
        json_logs=settings.json_logs_enabled,
    )
    application = FastAPI(title=settings.app_name, lifespan=app_lifespan)
    if settings.cors_allowed_origins_list:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_error_handlers(application)
    configure_telemetry(application, settings)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app()
