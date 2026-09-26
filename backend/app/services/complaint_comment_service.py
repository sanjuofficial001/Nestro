"""Business logic for complaint comment threads.

A comment is an immutable message in a complaint's discussion, so this service does
two things and delegates the rest: it resolves and authorizes the parent complaint
(reusing `ComplaintService.get_complaint`, which already answers 404 for a missing
complaint and 403 for a caller outside the complaint's organization), and it owns
the author's identity.

**Who may post.** Any organization member — OWNER, MANAGER, or STAFF — plus the
platform-wide SUPER_ADMIN, matching API_SPEC endpoint 53's "member" for the
org-scoped surface. Tenant posting is deferred: there is no tenant-facing
complaint access yet, and `OrganizationRoleEnum` has no `TENANT` member, so a
resident cannot reach this service at all.

That makes `get_complaint`'s guard the *post* guard as well, so there is no second
role check here to drift out of sync: posting and reading are the same permission
set, and the moment they diverge the guard has to move rather than be duplicated.
`ComplaintService._READ` is `require_org_roles(*OrganizationRoleEnum)`, which is
exactly the "all members may post" rule.

**`is_internal` is stored but not filtered.** API_SPEC endpoint 53 accepts the
flag and note 209 requires tenant-invisible internal notes, so the column is
persisted, validated, returned, and tested. Visibility filtering is deferred until
tenant-facing complaint access exists: every caller who can reach these methods is
a staff-side role that is allowed to read internal notes, so a `can_view_internal`
branch would be unreachable and untestable today.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.complaint_comment import ComplaintComment
from app.models.user import User
from app.repositories.complaint_comment import ComplaintCommentRepository
from app.schemas.complaint_comment import ComplaintCommentCreate
from app.services.complaint_service import ComplaintService


class ComplaintCommentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._complaints = ComplaintService(session)
        self._comments = ComplaintCommentRepository(session)

    def list_comments(self, user: User, complaint_id: UUID) -> list[ComplaintComment]:
        """A thread in conversation order, oldest first.

        The complaint is resolved through `ComplaintService` first, and that is what
        supplies the organization check: a missing complaint is a 404, and an
        authenticated caller who is not a member of the complaint's organization is
        a 403 — the same answers the shipped complaint endpoints give. (That 403 also
        means a caller who already holds a complaint id can tell "exists" from
        "does not exist". It is pre-existing `ComplaintService` behaviour and is
        left alone here; closing it means returning 404 for a foreign complaint,
        which changes the shipped complaint endpoints too.)
        """
        self._complaints.get_complaint(user, complaint_id)
        return self._comments.list_for_complaint(complaint_id)

    def create_comment(
        self, user: User, complaint_id: UUID, payload: ComplaintCommentCreate
    ) -> ComplaintComment:
        self._complaints.get_complaint(user, complaint_id)
        return self._comments.create(
            complaint_id=complaint_id,
            user_id=user.id,
            body=payload.body,
            is_internal=payload.is_internal,
        )
