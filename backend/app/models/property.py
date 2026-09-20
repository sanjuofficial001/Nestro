"""Property model — the venue (PG, hostel, hotel, apartment, co-living)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PropertyStatusEnum, PropertyTypeEnum

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.organization import Organization
    from app.models.resident_profile import ResidentProfile
    from app.models.tenant_stay import TenantStay


class Property(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "properties"

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    property_type: Mapped[PropertyTypeEnum] = mapped_column(
        Enum(PropertyTypeEnum, name="property_type"),
        nullable=False,
        index=True,
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PropertyStatusEnum] = mapped_column(
        Enum(PropertyStatusEnum, name="property_status"),
        nullable=False,
        default=PropertyStatusEnum.ACTIVE,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship(back_populates="properties")
    buildings: Mapped[list[Building]] = relationship(back_populates="property")
    resident_profiles: Mapped[list[ResidentProfile]] = relationship(
        back_populates="property"
    )
    tenant_stays: Mapped[list[TenantStay]] = relationship(back_populates="property")

    def __repr__(self) -> str:
        return f"<Property id={self.id!r} name={self.name!r} type={self.property_type.value}>"