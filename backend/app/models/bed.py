"""Bed model — a single bed within a room.

The bed rows owned by a room define its capacity: a room with 20 beds seats 20
people (dorm), a room with 2 beds is a double, and so on. Nothing capacity-like
is stored on `Room`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BedStatusEnum

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.tenant_stay import TenantStay


class Bed(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "beds"
    __table_args__ = (UniqueConstraint("room_id", "bed_number"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    room_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("rooms.id"), nullable=False, index=True
    )
    bed_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[BedStatusEnum] = mapped_column(
        Enum(BedStatusEnum, name="bed_status"),
        nullable=False,
        default=BedStatusEnum.AVAILABLE,
        index=True,
    )

    room: Mapped[Room] = relationship(back_populates="beds")
    tenant_stays: Mapped[list[TenantStay]] = relationship(back_populates="bed")

    def __repr__(self) -> str:
        return f"<Bed id={self.id!r} number={self.bed_number!r} status={self.status.value}>"