"""Persistence layer.

Contains the declarative Base (with a fixed naming convention) that Alembic
targets for autogenerate, the lazily-initialized engine and session factory,
the TimestampMixin / UUIDPrimaryKeyMixin for domain models, and a database
reachability check.
"""

from app.db.base import NAMING_CONVENTION, Base
from app.db.health import check_database_connection, mask_database_url
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.session import SessionLocal, get_db, get_engine

__all__ = [
    "Base",
    "NAMING_CONVENTION",
    "SessionLocal",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "check_database_connection",
    "get_db",
    "get_engine",
    "mask_database_url",
]