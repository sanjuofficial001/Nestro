"""Nestro FastAPI application entrypoint.

Application is built by `create_application()` and exposed as the module-level
`app` for `uvicorn app.main:app` and test clients.
"""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.api.v1.routes.health import router as health_router
from app.core.config import settings
from app.core.handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import configure_logging


def create_application() -> FastAPI:
    configure_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_application()