"""Reusable ORM mixins."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


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