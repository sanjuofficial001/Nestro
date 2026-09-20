"""ResidentProfile model — a tenant's residency profile inside an organization.

A resident is represented by an `OrganizationMember` row in the organization
they live in; the profile references that membership (`organization_member_id`),
never the raw user. This keeps platform identity on `users` and residency data
on the profile — the chain is User → Organization Member → Resident Profile
(see docs/DATABASE.md §14). Bed assignment and stays ship in later milestones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.organization_member import OrganizationMember
    from app.models.property import Property


class ResidentProfile(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "resident_profiles"
    __table_args__ = (UniqueConstraint("organization_member_id"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    organization_member_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organization_members.id"), nullable=False
    )
    property_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("properties.id"), nullable=True, index=True
    )
    emergency_contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    emergency_contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship(
        back_populates="resident_profiles"
    )
    organization_member: Mapped[OrganizationMember] = relationship(
        back_populates="resident_profile"
    )
    property: Mapped[Property | None] = relationship(back_populates="resident_profiles")

    def __repr__(self) -> str:
        return f"<ResidentProfile id={self.id!r} member={self.organization_member_id!r}>"