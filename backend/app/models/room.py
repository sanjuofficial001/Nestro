"""Room model — a room within a floor.

A room never stores a capacity value. Its capacity is always derived from the
number of `Bed` rows that reference it (`COUNT(beds.id)`); a room can hold any
number of beds without a schema change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RoomTypeEnum

if TYPE_CHECKING:
    from app.models.bed import Bed
    from app.models.floor import Floor


class Room(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("floor_id", "room_number"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    floor_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("floors.id"), nullable=False, index=True
    )
    room_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    room_type: Mapped[RoomTypeEnum] = mapped_column(
        Enum(RoomTypeEnum, name="room_type"), nullable=False
    )

    floor: Mapped[Floor] = relationship(back_populates="rooms")
    beds: Mapped[list[Bed]] = relationship(back_populates="room")

    def __repr__(self) -> str:
        return f"<Room id={self.id!r} number={self.room_number!r} type={self.room_type.value}>"