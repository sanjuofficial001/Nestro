"""Business logic for org-scoped complaint CRUD.

A complaint is triage state for an issue a resident raised about a property, so
every reference on it is resolved and ownership-checked before it is stored, and
every operation is gated on the caller's membership in the complaint's
organization. Authorization mirrors the Property/Building/ResidentProfile/
TenantStay APIs: OWNER/MANAGER write, any member reads, and the platform-wide
SUPER_ADMIN role bypasses membership.

Status is a workflow, not a free field. The order in `ComplaintStatusEnum` is the
workflow order, and an update may only stay put, step one forward, or step one
backward; `CLOSED` is terminal. `category`, `organization_id`, `property_id`,
and `resident_profile_id` are structurally immutable (`ComplaintUpdate` does not
accept them), and `resolved_at` is not written here.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.api.permissions import require_org_roles
from app.core.exceptions import NotFoundError
from app.models.complaint import Complaint
from app.models.enums import (
    ComplaintPriorityEnum,
    ComplaintStatusEnum,
    OrganizationRoleEnum,
)
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.complaint import ComplaintRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.schemas.complaint import ComplaintCreate
from app.schemas.complaint_api import ComplaintUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)

_STATUS_ORDER = tuple(ComplaintStatusEnum)


class ComplaintService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._complaints = ComplaintRepository(session)
        self._profiles = ResidentProfileRepository(session)
        self._properties = PropertyRepository(session)
        self._members = OrganizationMemberRepository(session)

    def create_complaint(self, user: User, payload: ComplaintCreate) -> Complaint:
        _WRITE(user, self._memberships_for(user.id, payload.organization_id))
        self._check_property(payload.property_id, payload.organization_id)
        self._check_resident(payload.resident_profile_id, payload.organization_id)
        if payload.assigned_to_member_id is not None:
            self._check_assignee(payload.assigned_to_member_id, payload.organization_id)
        return self._complaints.create(payload)

    def list_complaints(
        self,
        user: User,
        organization_id: UUID,
        status: ComplaintStatusEnum | None = None,
        priority: ComplaintPriorityEnum | None = None,
        resident_profile_id: UUID | None = None,
    ) -> list[Complaint]:
        _READ(user, self._memberships_for(user.id, organization_id))
        if resident_profile_id is not None:
            self._require_resident_in_org(resident_profile_id, organization_id)
        return self._complaints.list_for_org(
            organization_id, status, priority, resident_profile_id
        )

    def get_complaint(self, user: User, complaint_id: UUID) -> Complaint:
        complaint = self._complaints.get_by_id(complaint_id)
        if complaint is None:
            raise NotFoundError(detail="complaint not found")
        _READ(user, self._memberships_for(user.id, complaint.organization_id))
        return complaint

    def update_complaint(
        self, user: User, complaint_id: UUID, payload: ComplaintUpdate
    ) -> Complaint:
        complaint = self.get_complaint(user, complaint_id)
        _WRITE(user, self._memberships_for(user.id, complaint.organization_id))

        changes = payload.model_dump(exclude_unset=True)
        if "status" in changes:
            self._check_transition(complaint.status, changes["status"])
        if payload.assigned_to_member_id is not None:
            self._check_assignee(
                payload.assigned_to_member_id, complaint.organization_id
            )

        for field, value in changes.items():
            if value is not None:
                setattr(complaint, field, value)
        self._session.commit()
        self._session.refresh(complaint)
        return complaint

    def _check_transition(
        self, current: ComplaintStatusEnum, target: ComplaintStatusEnum
    ) -> None:
        if target == current:
            return
        if current == ComplaintStatusEnum.CLOSED:
            raise ValueError("a closed complaint cannot be reopened")
        step = abs(_STATUS_ORDER.index(target) - _STATUS_ORDER.index(current))
        if step > 1:
            raise ValueError("invalid complaint status transition")

    def _check_resident(
        self, resident_profile_id: UUID, organization_id: UUID
    ) -> None:
        profile = self._profiles.get_by_id(resident_profile_id)
        if profile is None:
            raise NotFoundError(detail="resident profile not found")
        if profile.organization_id != organization_id:
            raise ValueError("resident profile does not belong to this organization")

    def _require_resident_in_org(
        self, resident_profile_id: UUID, organization_id: UUID
    ) -> None:
        """A list filter answers 404 for a foreign-org id exactly like a missing one, so
        filtering never reveals that a resident profile exists in another tenant."""
        profile = self._profiles.get_by_id(resident_profile_id)
        if profile is None or profile.organization_id != organization_id:
            raise NotFoundError(detail="resident profile not found")

    def _check_property(self, property_id: UUID, organization_id: UUID) -> None:
        prop = self._properties.get_by_id(property_id)
        if prop is None:
            raise NotFoundError(detail="property not found")
        if prop.organization_id != organization_id:
            raise ValueError("property does not belong to this organization")

    def _check_assignee(self, member_id: UUID, organization_id: UUID) -> None:
        member = self._members.get_by_id(member_id)
        if member is None:
            raise NotFoundError(detail="organization member not found")
        if member.organization_id != organization_id:
            raise ValueError("organization member does not belong to this organization")

    def _memberships_for(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [
            member
            for member in self._members.get_for_user(user_id)
            if member.organization_id == organization_id
        ]
