"""Complaint model — an issue a resident raises about the accommodation.

A complaint records what (`category`, `title`, `description`), how urgent it is
(`priority`), where it belongs (`organization_id` + `property_id` + the raising
`resident_profile_id`), who is handling it (`assigned_to_member_id`, scoped to an
organization membership rather than a bare user id so a user who belongs to
several organizations stays unambiguous), and where triage stands (`status`).

`resolved_at` is recorded by DATABASE.md §19 and is intentionally left unwritten
in this milestone — stamping it belongs to the workflow milestone, together with
`complaint_comments` (§20) and the reopen audit.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ComplaintCategoryEnum,
    ComplaintPriorityEnum,
    ComplaintStatusEnum,
)

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.organization_member import OrganizationMember
    from app.models.property import Property
    from app.models.resident_profile import ResidentProfile


class Complaint(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "complaints"

    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    property_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("properties.id"), nullable=False, index=True
    )
    resident_profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resident_profiles.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[ComplaintCategoryEnum] = mapped_column(
        Enum(ComplaintCategoryEnum, name="complaint_category"), nullable=False
    )
    priority: Mapped[ComplaintPriorityEnum] = mapped_column(
        Enum(ComplaintPriorityEnum, name="complaint_priority"),
        nullable=False,
        default=ComplaintPriorityEnum.MEDIUM,
        index=True,
    )
    status: Mapped[ComplaintStatusEnum] = mapped_column(
        Enum(ComplaintStatusEnum, name="complaint_status"),
        nullable=False,
        default=ComplaintStatusEnum.OPEN,
        index=True,
    )
    assigned_to_member_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("organization_members.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship(back_populates="complaints")
    property: Mapped[Property] = relationship(back_populates="complaints")
    resident_profile: Mapped[ResidentProfile] = relationship(
        back_populates="complaints"
    )
    assigned_to_member: Mapped[OrganizationMember | None] = relationship(
        back_populates="complaints"
    )

    def __repr__(self) -> str:
        return (
            f"<Complaint id={self.id!r} category={self.category.value} "
            f"status={self.status.value}>"
        )
