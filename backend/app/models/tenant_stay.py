"""TenantStay model — occupancy of a bed by a resident for a period of time.

A stay records where (property bed), who (resident profile), and when (start /
end date). `status` distinguishes an open stay (`ACTIVE`, no `end_date`) from a
closed one (`COMPLETED` / `CANCELLED`). At most one `ACTIVE` stay may exist per
bed, enforced by the partial unique index `uq_tenant_stays_active_bed` on
`bed_id WHERE status = 'ACTIVE'` — not by a `UNIQUE(bed_id, status)` constraint,
which would block recording a second completed stay on the same bed.

Security deposits and payments are out of scope (see docs/DATABASE.md §15); the
stay keeps occupancy history only.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TenantStayStatusEnum

if TYPE_CHECKING:
    from app.models.bed import Bed
    from app.models.organization import Organization
    from app.models.property import Property
    from app.models.resident_profile import ResidentProfile


class TenantStay(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tenant_stays"
    __table_args__ = (
        Index(
            "uq_tenant_stays_active_bed",
            "bed_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    resident_profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resident_profiles.id"), nullable=False, index=True
    )
    property_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("properties.id"), nullable=False
    )
    bed_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("beds.id"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TenantStayStatusEnum] = mapped_column(
        Enum(TenantStayStatusEnum, name="tenant_stay_status"),
        nullable=False,
        default=TenantStayStatusEnum.ACTIVE,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="tenant_stays")
    resident_profile: Mapped[ResidentProfile] = relationship(
        back_populates="tenant_stays"
    )
    property: Mapped[Property] = relationship(back_populates="tenant_stays")
    bed: Mapped[Bed] = relationship(back_populates="tenant_stays")

    def __repr__(self) -> str:
        return (
            f"<TenantStay id={self.id!r} bed={self.bed_id!r} "
            f"status={self.status.value}>"
        )