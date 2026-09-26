"""Data access for complaint comments. Repository layer only — no services, no endpoints.

**Organization scope comes from the parent complaint.** `complaint_comments` has no
`organization_id` column (see `app/models/complaint_comment.py` for why), so this
repository cannot filter by organization on its own. It is deliberately not given
the ability to: every method here takes a `complaint_id` that the service has
already resolved and authorized against `complaints.organization_id`. There is no
"list all comments" method, so there is no unscoped read path.

`include_internal` is deliberately absent: every caller of these endpoints is a
staff-side role, so a visibility branch would be unreachable today. It lands with
tenant-facing complaint access.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.complaint_comment import ComplaintComment


class ComplaintCommentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_complaint(self, complaint_id: UUID) -> list[ComplaintComment]:
        """One thread in conversation order — oldest first."""
        query = select(ComplaintComment).where(
            ComplaintComment.complaint_id == complaint_id
        )
        return list(
            self._session.scalars(query.order_by(ComplaintComment.created_at.asc()))
        )

    def get_by_id(self, comment_id: UUID) -> ComplaintComment | None:
        return self._session.get(ComplaintComment, comment_id)

    def create(
        self,
        *,
        complaint_id: UUID,
        user_id: UUID,
        body: str,
        is_internal: bool,
    ) -> ComplaintComment:
        """`body` is the API field name; the column is `comment` (DATABASE.md §20),
        so the mapping is explicit here rather than a `model_dump()` splat."""
        comment = ComplaintComment(
            complaint_id=complaint_id,
            user_id=user_id,
            comment=body,
            is_internal=is_internal,
        )
        self._session.add(comment)
        self._session.commit()
        self._session.refresh(comment)
        return comment
