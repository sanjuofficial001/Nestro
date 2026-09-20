"""Nestro FastAPI application entrypoint.

Mounts the versioned API router under the configured prefix and exposes the
unversioned health probe at the root for load balancers and platform health checks.
"""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.api.v1.routes.health import router as health_router
from app.core.config import settings

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(api_router, prefix=settings.api_v1_prefix)