"""Reusable ORM mixins."""

import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """UUID primary key.

    Every Nestro table keys on UUID (see DATABASE.md). The value defaults
    client-side to `uuid.uuid4` — a PostgreSQL-compatible choice that also keeps
    SQLite-based tests portable.
    """

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Server-managed `created_at` / `updated_at` columns.

    Both are timezone-aware UTC timestamps populated by the database
    (`server_default=func.now()`). `updated_at` is refreshed automatically by
    the database on every UPDATE (`onupdate`).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )