"""Application lifespan: startup and shutdown hooks.

Startup verifies database reachability: the mirrored URL is logged, and the app
fails to start in staging/production if the database is unreachable while
development continues with a warning.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI

from app.core.config import get_settings
from app.db.health import check_database_connection, mask_database_url

logger = getLogger("nestro")


def _verify_database_at_startup() -> None:
    logger.info("Database configured: %s", mask_database_url())
    if check_database_connection():
        logger.info("Database connection healthy")
        return
    if get_settings().environment == "development":
        logger.warning("Database unavailable at startup — continuing in development")
        return
    raise RuntimeError(
        f"Database unavailable in {get_settings().environment} environment"
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Application starting")
    _verify_database_at_startup()
    yield
    logger.info("Application shutting down")