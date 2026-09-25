"""Business logic for org-scoped building CRUD.

Every operation first resolves the caller's membership in the target
organization and enforces the required `OrganizationRoleEnum` roles through
`require_org_roles`; write access is OWNER/MANAGER, reads are any member.
The platform-wide SUPER_ADMIN role bypasses membership entirely.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.api.permissions import require_org_roles
from app.core.exceptions import NotFoundError
from app.models.building import Building
from app.models.enums import OrganizationRoleEnum
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.building import BuildingRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.schemas.building import BuildingCreate
from app.schemas.building_api import BuildingUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)


class BuildingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._buildings = BuildingRepository(session)
        self._properties = PropertyRepository(session)
        self._members = OrganizationMemberRepository(session)

    def create_building(self, user: User, payload: BuildingCreate) -> Building:
        _WRITE(user, self._memberships_for(user.id, payload.organization_id))
        property = self._properties.get_by_id(payload.property_id)
        if property is None:
            raise NotFoundError(detail="property not found")
        if property.organization_id != payload.organization_id:
            raise ValueError("property does not belong to this organization")
        if self._buildings.exists_by_name(payload.property_id, payload.name):
            raise ValueError("building already exists")
        return self._buildings.create(payload)

    def list_buildings(
        self, user: User, organization_id: UUID, property_id: UUID
    ) -> list[Building]:
        _READ(user, self._memberships_for(user.id, organization_id))
        property = self._properties.get_by_id(property_id)
        if property is None or property.organization_id != organization_id:
            raise NotFoundError(detail="property not found")
        return self._buildings.list_for_property(property_id)

    def get_building(self, user: User, building_id: UUID) -> Building:
        building = self._buildings.get_by_id(building_id)
        if building is None:
            raise NotFoundError(detail="building not found")
        _READ(user, self._memberships_for(user.id, building.organization_id))
        return building

    def update_building(
        self, user: User, building_id: UUID, payload: BuildingUpdate
    ) -> Building:
        building = self.get_building(user, building_id)
        _WRITE(user, self._memberships_for(user.id, building.organization_id))
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(building, field, value)
        self._session.commit()
        self._session.refresh(building)
        return building

    def _memberships_for(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [
            member
            for member in self._members.get_for_user(user_id)
            if member.organization_id == organization_id
        ]