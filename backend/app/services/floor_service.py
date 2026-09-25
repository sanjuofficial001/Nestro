"""Business logic for org-scoped floor CRUD.

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
from app.models.floor import Floor
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.schemas.floor import FloorCreate
from app.schemas.floor_api import FloorUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)


class FloorService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._floors = FloorRepository(session)
        self._buildings = BuildingRepository(session)
        self._members = OrganizationMemberRepository(session)

    def create_floor(self, user: User, payload: FloorCreate) -> Floor:
        _WRITE(user, self._memberships_for(user.id, payload.organization_id))
        building = self._buildings.get_by_id(payload.building_id)
        if building is None:
            raise NotFoundError(detail="building not found")
        if building.organization_id != payload.organization_id:
            raise ValueError("building does not belong to this organization")
        if self._floors.exists_by_number(payload.building_id, payload.floor_number):
            raise ValueError("floor already exists")
        return self._floors.create(payload)

    def list_floors(
        self, user: User, organization_id: UUID, building_id: UUID
    ) -> list[Floor]:
        _READ(user, self._memberships_for(user.id, organization_id))
        building = self._buildings.get_by_id(building_id)
        if building is None or building.organization_id != organization_id:
            raise NotFoundError(detail="building not found")
        return self._floors.list_for_building(building_id)

    def get_floor(self, user: User, floor_id: UUID) -> Floor:
        floor = self._floors.get_by_id(floor_id)
        if floor is None:
            raise NotFoundError(detail="floor not found")
        _READ(user, self._memberships_for(user.id, floor.organization_id))
        return floor

    def update_floor(
        self, user: User, floor_id: UUID, payload: FloorUpdate
    ) -> Floor:
        floor = self.get_floor(user, floor_id)
        _WRITE(user, self._memberships_for(user.id, floor.organization_id))
        if (
            payload.floor_number is not None
            and payload.floor_number != floor.floor_number
            and self._floors.exists_by_number(
                floor.building_id,
                payload.floor_number,
            )
        ):
            raise ValueError("floor already exists")
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(floor, field, value)
        self._session.commit()
        self._session.refresh(floor)
        return floor

    def _memberships_for(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [
            member
            for member in self._members.get_for_user(user_id)
            if member.organization_id == organization_id
        ]