"""Application lifespan: startup and shutdown hooks.

Architecture-only for now — no database connections or external services
are initialized. Future milestones add their own lifecycle work here.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI

logger = getLogger("nestro")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Application starting")
    yield
    logger.info("Application shutting down")