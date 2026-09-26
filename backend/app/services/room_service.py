"""Business logic for org-scoped room CRUD.

Every operation first resolves the caller's membership in the target
organization and enforces the required `OrganizationRoleEnum` roles through
`require_org_roles`; write access is OWNER/MANAGER, reads are any member.
The platform-wide SUPER_ADMIN role bypasses membership entirely.

Capacity is never read from `Room`; a room's size is the count of its `Bed`
rows (`COUNT(beds.id)`), computed when occupancy milestones need it.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.api.permissions import require_org_roles
from app.core.exceptions import NotFoundError
from app.models.enums import OrganizationRoleEnum
from app.models.organization_member import OrganizationMember
from app.models.room import Room
from app.models.user import User
from app.repositories.floor import FloorRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.room import RoomRepository
from app.schemas.room import RoomCreate
from app.schemas.room_api import RoomUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)


class RoomService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._rooms = RoomRepository(session)
        self._floors = FloorRepository(session)
        self._members = OrganizationMemberRepository(session)

    def create_room(self, user: User, payload: RoomCreate) -> Room:
        _WRITE(user, self._memberships_for(user.id, payload.organization_id))
        floor = self._floors.get_by_id(payload.floor_id)
        if floor is None:
            raise NotFoundError(detail="floor not found")
        if floor.organization_id != payload.organization_id:
            raise ValueError("floor does not belong to this organization")
        if self._rooms.exists_by_number(payload.floor_id, payload.room_number):
            raise ValueError("room already exists")
        return self._rooms.create(payload)

    def list_rooms(
        self, user: User, organization_id: UUID, floor_id: UUID
    ) -> list[Room]:
        _READ(user, self._memberships_for(user.id, organization_id))
        floor = self._floors.get_by_id(floor_id)
        if floor is None or floor.organization_id != organization_id:
            raise NotFoundError(detail="floor not found")
        return self._rooms.list_for_floor(floor_id)

    def get_room(self, user: User, room_id: UUID) -> Room:
        room = self._rooms.get_by_id(room_id)
        if room is None:
            raise NotFoundError(detail="room not found")
        _READ(user, self._memberships_for(user.id, room.organization_id))
        return room

    def update_room(self, user: User, room_id: UUID, payload: RoomUpdate) -> Room:
        room = self.get_room(user, room_id)
        _WRITE(user, self._memberships_for(user.id, room.organization_id))
        if (
            payload.room_number is not None
            and payload.room_number != room.room_number
            and self._rooms.exists_by_number(
                room.floor_id,
                payload.room_number,
            )
        ):
            raise ValueError("room already exists")
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(room, field, value)
        self._session.commit()
        self._session.refresh(room)
        return room

    def _memberships_for(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [
            member
            for member in self._members.get_for_user(user_id)
            if member.organization_id == organization_id
        ]