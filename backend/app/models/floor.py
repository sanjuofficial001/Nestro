"""Floor model — a level within a building."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.room import Room


class Floor(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "floors"
    __table_args__ = (UniqueConstraint("building_id", "floor_number"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    building_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("buildings.id"), nullable=False, index=True
    )
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    building: Mapped[Building] = relationship(back_populates="floors")
    rooms: Mapped[list[Room]] = relationship(back_populates="floor")

    def __repr__(self) -> str:
        return f"<Floor id={self.id!r} number={self.floor_number!r}>"