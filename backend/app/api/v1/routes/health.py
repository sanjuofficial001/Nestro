"""Liveness probe.

Mounted twice in the app entrypoint: at the root for load balancers and platform
health checks, and under the API v1 prefix for versioned consumers. Both registrations
point at this single handler.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(environment=settings.environment)