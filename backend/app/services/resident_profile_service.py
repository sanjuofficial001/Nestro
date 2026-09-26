"""Business logic for org-scoped resident profile CRUD.

A profile belongs to an organization and to exactly one membership in it
(`UNIQUE (organization_member_id)`), so the chain is User -> OrganizationMember
-> ResidentProfile. Every operation first resolves the caller's membership in the
target organization and enforces the required `OrganizationRoleEnum` roles
through `require_org_roles`; write access is OWNER/MANAGER, reads are any
member. The platform-wide SUPER_ADMIN role bypasses membership entirely.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.api.permissions import require_org_roles
from app.core.exceptions import NotFoundError
from app.models.enums import OrganizationRoleEnum
from app.models.organization_member import OrganizationMember
from app.models.resident_profile import ResidentProfile
from app.models.user import User
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.resident_profile_api import ResidentProfileUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)


class ResidentProfileService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._profiles = ResidentProfileRepository(session)
        self._members = OrganizationMemberRepository(session)
        self._properties = PropertyRepository(session)

    def create_resident_profile(
        self, user: User, payload: ResidentProfileCreate
    ) -> ResidentProfile:
        _WRITE(user, self._memberships_for(user.id, payload.organization_id))
        member = self._members.get_by_id(payload.organization_member_id)
        if member is None:
            raise NotFoundError(detail="organization member not found")
        if member.organization_id != payload.organization_id:
            raise ValueError("organization member does not belong to this organization")
        if payload.property_id is not None:
            self._check_property(payload.property_id, payload.organization_id)
        if self._profiles.exists_for_member(payload.organization_member_id):
            raise ValueError("resident profile already exists")
        return self._profiles.create(payload)

    def list_resident_profiles(
        self, user: User, organization_id: UUID
    ) -> list[ResidentProfile]:
        _READ(user, self._memberships_for(user.id, organization_id))
        return self._profiles.list_for_org(organization_id)

    def get_resident_profile(self, user: User, profile_id: UUID) -> ResidentProfile:
        profile = self._profiles.get_by_id(profile_id)
        if profile is None:
            raise NotFoundError(detail="resident profile not found")
        _READ(user, self._memberships_for(user.id, profile.organization_id))
        return profile

    def update_resident_profile(
        self, user: User, profile_id: UUID, payload: ResidentProfileUpdate
    ) -> ResidentProfile:
        profile = self.get_resident_profile(user, profile_id)
        _WRITE(user, self._memberships_for(user.id, profile.organization_id))
        if (
            payload.property_id is not None
            and payload.property_id != profile.property_id
        ):
            self._check_property(payload.property_id, profile.organization_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(profile, field, value)
        self._session.commit()
        self._session.refresh(profile)
        return profile

    def _check_property(self, property_id: UUID, organization_id: UUID) -> None:
        prop = self._properties.get_by_id(property_id)
        if prop is None:
            raise NotFoundError(detail="property not found")
        if prop.organization_id != organization_id:
            raise ValueError("property does not belong to this organization")

    def _memberships_for(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [
            member
            for member in self._members.get_for_user(user_id)
            if member.organization_id == organization_id
        ]