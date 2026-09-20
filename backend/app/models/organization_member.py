"""Organization membership model — connects users to organizations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import OrganizationRoleEnum

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.resident_profile import ResidentProfile
    from app.models.user import User


class OrganizationMember(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[OrganizationRoleEnum] = mapped_column(
        Enum(OrganizationRoleEnum, name="organization_role"), nullable=False
    )

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="members")
    resident_profile: Mapped[ResidentProfile | None] = relationship(
        back_populates="organization_member"
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationMember org={self.organization_id!r} "
            f"user={self.user_id!r} role={self.role.value}>"
        )