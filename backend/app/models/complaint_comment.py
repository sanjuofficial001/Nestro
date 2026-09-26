"""Complaint comment model — one immutable message in a complaint's thread.

DATABASE.md §20 defines this table as `complaint_comments(id, complaint_id,
user_id, comment, created_at)`, plus one intentional extension:

- `is_internal` (BOOLEAN NOT NULL DEFAULT false) — API_SPEC endpoint 53 accepts
  `is_internal` on create, so the flag must be persisted. See the note on
  visibility filtering below.

Three deliberate deviations from the DATABASE.md conventions, each for a reason:

- **No `organization_id`.** "Multi-Tenant First" and §28 ask every business table
  to carry it, but organization scope is already authoritative on the parent
  complaint (`complaint_comments.complaint_id -> complaints.organization_id`).
  A second tenancy column on the child could only ever disagree with the parent,
  so reads and writes resolve the parent complaint first and authorize there.
- **`user_id`, not `organization_member_id`.** Comment authorship is a user
  action. `assigned_to_member_id` on `complaints` is assignment metadata and
  exists to disambiguate *which* organization an assignment was made in; the
  comment's organization is already implied by its complaint, so the raw user id
  is unambiguous here.
- **`created_at` only, no `updated_at`.** §20 lists no `updated_at` and comments
  are immutable — there is no edit or delete endpoint, so a mutation timestamp
  would never move. `TimestampMixin` is therefore not used.

**Visibility filtering is deferred.** `is_internal` is stored, validated, and
returned, but nothing filters on it yet: API access is org-member-only and
`OrganizationRoleEnum` has no `TENANT` member, so every caller who can reach
these endpoints is a staff-side role that is allowed to read internal notes. A
`can_view_internal` branch would be unreachable and untestable today. Filtering
arrives with tenant-facing complaint access.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.user import User


class ComplaintComment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "complaint_comments"

    complaint_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("complaints.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    complaint: Mapped[Complaint] = relationship(back_populates="comments")
    user: Mapped[User] = relationship(back_populates="comments")

    def __repr__(self) -> str:
        return (
            f"<ComplaintComment id={self.id!r} complaint={self.complaint_id!r} "
            f"user={self.user_id!r} internal={self.is_internal}>"
        )
