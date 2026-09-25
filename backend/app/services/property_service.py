"""Business logic for org-scoped property CRUD.

Every operation first resolves the caller's membership in the target
organization and enforces the required `OrganizationRoleEnum` roles through
`require_org_roles`; write access is OWNER/MANAGER, reads are any member.
The platform-wide SUPER_ADMIN role bypasses membership entirely.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.api.permissions import require_org_roles
from app.core.exceptions import NotFoundError
from app.models.enums import OrganizationRoleEnum
from app.models.organization_member import OrganizationMember
from app.models.property import Property
from app.models.user import User
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.schemas.property import PropertyCreate
from app.schemas.property_api import PropertyUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)


class PropertyService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._properties = PropertyRepository(session)
        self._members = OrganizationMemberRepository(session)

    def create_property(self, user: User, payload: PropertyCreate) -> Property:
        memberships = self._memberships_for(user.id, payload.organization_id)
        _WRITE(user, memberships)
        if self._properties.exists_by_name(payload.organization_id, payload.name):
            raise ValueError("property already exists")
        return self._properties.create(payload)

    def list_properties(self, user: User, organization_id: UUID) -> list[Property]:
        _READ(user, self._memberships_for(user.id, organization_id))
        return self._properties.list_for_org(organization_id)

    def get_property(self, user: User, property_id: UUID) -> Property:
        property = self._properties.get_by_id(property_id)
        if property is None:
            raise NotFoundError()
        _READ(user, self._memberships_for(user.id, property.organization_id))
        return property

    def update_property(
        self, user: User, property_id: UUID, payload: PropertyUpdate
    ) -> Property:
        property = self.get_property(user, property_id)
        _WRITE(user, self._memberships_for(user.id, property.organization_id))
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(property, field, value)
        self._session.commit()
        self._session.refresh(property)
        return property

    def _memberships_for(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [
            member
            for member in self._members.get_for_user(user_id)
            if member.organization_id == organization_id
        ]