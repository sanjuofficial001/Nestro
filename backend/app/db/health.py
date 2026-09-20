"""Database reachability checks and URL reporting."""

import logging
from typing import Final

from sqlalchemy import text

from app.db.session import get_engine

logger: Final = logging.getLogger("nestro.db.health")


def mask_database_url() -> str:
    """Render the configured database URL with the password hidden."""
    return get_engine().url.render_as_string(hide_password=True)


def check_database_connection() -> bool:
    """Return True if the database answers `SELECT 1`, logging failures."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database connection check failed")
        return False
    return True