"""Organization model — top-level tenant boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization_member import OrganizationMember
    from app.models.property import Property
    from app.models.resident_profile import ResidentProfile


class Organization(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list[OrganizationMember]] = relationship(
        back_populates="organization"
    )
    properties: Mapped[list[Property]] = relationship(back_populates="organization")
    resident_profiles: Mapped[list[ResidentProfile]] = relationship(
        back_populates="organization"
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id!r} slug={self.slug!r}>"