"""Business logic for org-scoped bed CRUD.

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
from app.models.bed import Bed
from app.models.enums import OrganizationRoleEnum
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.bed import BedRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.room import RoomRepository
from app.schemas.bed import BedCreate
from app.schemas.bed_api import BedUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)


class BedService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._beds = BedRepository(session)
        self._rooms = RoomRepository(session)
        self._members = OrganizationMemberRepository(session)

    def create_bed(self, user: User, payload: BedCreate) -> Bed:
        _WRITE(user, self._memberships_for(user.id, payload.organization_id))
        room = self._rooms.get_by_id(payload.room_id)
        if room is None:
            raise NotFoundError(detail="room not found")
        if room.organization_id != payload.organization_id:
            raise ValueError("room does not belong to this organization")
        if self._beds.exists_by_number(payload.room_id, payload.bed_number):
            raise ValueError("bed already exists")
        return self._beds.create(payload)

    def list_beds(self, user: User, organization_id: UUID, room_id: UUID) -> list[Bed]:
        _READ(user, self._memberships_for(user.id, organization_id))
        room = self._rooms.get_by_id(room_id)
        if room is None or room.organization_id != organization_id:
            raise NotFoundError(detail="room not found")
        return self._beds.list_for_room(room_id)

    def get_bed(self, user: User, bed_id: UUID) -> Bed:
        bed = self._beds.get_by_id(bed_id)
        if bed is None:
            raise NotFoundError(detail="bed not found")
        _READ(user, self._memberships_for(user.id, bed.organization_id))
        return bed

    def update_bed(self, user: User, bed_id: UUID, payload: BedUpdate) -> Bed:
        bed = self.get_bed(user, bed_id)
        _WRITE(user, self._memberships_for(user.id, bed.organization_id))
        if (
            payload.bed_number is not None
            and payload.bed_number != bed.bed_number
            and self._beds.exists_by_number(
                bed.room_id,
                payload.bed_number,
            )
        ):
            raise ValueError("bed already exists")
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(bed, field, value)
        self._session.commit()
        self._session.refresh(bed)
        return bed

    def _memberships_for(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [
            member
            for member in self._members.get_for_user(user_id)
            if member.organization_id == organization_id
        ]