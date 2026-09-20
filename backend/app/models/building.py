"""Building model — a physical structure under a property."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.floor import Floor
    from app.models.property import Property


class Building(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "buildings"
    __table_args__ = (UniqueConstraint("property_id", "name"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    property_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("properties.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    property: Mapped[Property] = relationship(back_populates="buildings")
    floors: Mapped[list[Floor]] = relationship(back_populates="building")

    def __repr__(self) -> str:
        return f"<Building id={self.id!r} name={self.name!r}>"