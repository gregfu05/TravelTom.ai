"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_prefix)
