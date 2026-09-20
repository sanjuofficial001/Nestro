"""SQLAlchemy declarative base.

The single seam all ORM models inherit from and Alembic uses as its autogenerate
target metadata. Nothing else lives here — no engine, no session.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass