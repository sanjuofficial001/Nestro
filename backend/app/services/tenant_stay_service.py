"""Business logic for org-scoped tenant stay CRUD.

A stay records that a resident profile occupied a bed inside a property for a
period; occupancy is never stored on the resident or the bed. Every operation
first resolves the caller's membership in the target organization and enforces
the required `OrganizationRoleEnum` roles through `require_org_roles`; write
access is OWNER/MANAGER, reads are any member. The platform-wide SUPER_ADMIN
role bypasses membership entirely.

Lifecycle rules are validated against *effective* values (payload when supplied,
stored value otherwise) so a partial update can never leave a stay in an
incoherent state:

- `end_date` never precedes `start_date` (which is immutable);
- an `ACTIVE` stay has no `end_date`;
- a `COMPLETED` / `CANCELLED` stay always has one;
- a closed stay is never reopened (`COMPLETED` <-> `CANCELLED` is fine).

The database guarantees at most one `ACTIVE` stay per bed
(`uq_tenant_stays_active_bed`); the service checks `get_active_for_bed` up front
so a collision is a 409 conflict instead of an `IntegrityError`.
"""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.permissions import require_org_roles
from app.core.exceptions import NotFoundError
from app.models.bed import Bed
from app.models.enums import OrganizationRoleEnum, TenantStayStatusEnum
from app.models.organization_member import OrganizationMember
from app.models.tenant_stay import TenantStay
from app.models.user import User
from app.repositories.bed import BedRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.tenant_stay import TenantStayRepository
from app.schemas.tenant_stay import TenantStayCreate
from app.schemas.tenant_stay_api import TenantStayUpdate

_WRITE = require_org_roles(OrganizationRoleEnum.OWNER, OrganizationRoleEnum.MANAGER)
_READ = require_org_roles(*OrganizationRoleEnum)


class TenantStayService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._stays = TenantStayRepository(session)
        self._profiles = ResidentProfileRepository(session)
        self._beds = BedRepository(session)
        self._properties = PropertyRepository(session)
        self._members = OrganizationMemberRepository(session)

    def create_tenant_stay(self, user: User, payload: TenantStayCreate) -> TenantStay:
        _WRITE(user, self._memberships_for(user.id, payload.organization_id))
        self._check_lifecycle(payload.start_date, payload.end_date, payload.status)
        self._check_resident(payload.resident_profile_id, payload.organization_id)
        bed = self._check_bed(payload.bed_id, payload.organization_id)
        self._check_property(payload.property_id, payload.organization_id)
        if bed.room.floor.building.property_id != payload.property_id:
            raise ValueError("bed does not belong to the property")
        if (
            payload.status == TenantStayStatusEnum.ACTIVE
            and self._stays.get_active_for_bed(payload.bed_id) is not None
        ):
            raise ValueError("bed already has an active stay")
        return self._stays.create(payload)

    def list_tenant_stays(
        self,
        user: User,
        organization_id: UUID,
        resident_profile_id: UUID | None = None,
        bed_id: UUID | None = None,
        status: TenantStayStatusEnum | None = None,
    ) -> list[TenantStay]:
        _READ(user, self._memberships_for(user.id, organization_id))
        if resident_profile_id is not None:
            self._check_resident(resident_profile_id, organization_id)
        if bed_id is not None:
            self._check_bed(bed_id, organization_id)

        if resident_profile_id is not None:
            stays = self._stays.list_for_resident(resident_profile_id, status)
        elif bed_id is not None:
            stays = self._stays.list_for_bed(bed_id, status)
        else:
            stays = self._stays.list_for_org(organization_id, status)
        if resident_profile_id is not None and bed_id is not None:
            stays = [stay for stay in stays if stay.bed_id == bed_id]
        return stays

    def get_tenant_stay(self, user: User, stay_id: UUID) -> TenantStay:
        stay = self._stays.get_by_id(stay_id)
        if stay is None:
            raise NotFoundError(detail="tenant stay not found")
        _READ(user, self._memberships_for(user.id, stay.organization_id))
        return stay

    def update_tenant_stay(
        self, user: User, stay_id: UUID, payload: TenantStayUpdate
    ) -> TenantStay:
        stay = self.get_tenant_stay(user, stay_id)
        _WRITE(user, self._memberships_for(user.id, stay.organization_id))

        changes = payload.model_dump(exclude_unset=True)
        effective_status = changes.get("status", stay.status)
        effective_end_date = changes.get("end_date", stay.end_date)

        if (
            stay.status != TenantStayStatusEnum.ACTIVE
            and effective_status == TenantStayStatusEnum.ACTIVE
        ):
            raise ValueError("a closed stay cannot be reopened")
        self._check_lifecycle(stay.start_date, effective_end_date, effective_status)

        if (
            effective_status == TenantStayStatusEnum.ACTIVE
            and stay.status != TenantStayStatusEnum.ACTIVE
            and self._stays.get_active_for_bed(stay.bed_id) is not None
        ):
            raise ValueError("bed already has an active stay")

        for field, value in changes.items():
            if value is not None:
                setattr(stay, field, value)
        self._session.commit()
        self._session.refresh(stay)
        return stay

    def _check_lifecycle(
        self, start_date: date, end_date: date | None, status: TenantStayStatusEnum
    ) -> None:
        if end_date is not None and end_date < start_date:
            raise ValueError("end_date must not precede start_date")
        if status == TenantStayStatusEnum.ACTIVE and end_date is not None:
            raise ValueError("an active stay cannot have an end_date")
        if status != TenantStayStatusEnum.ACTIVE and end_date is None:
            raise ValueError("a closed stay requires an end_date")

    def _check_resident(
        self, resident_profile_id: UUID, organization_id: UUID
    ) -> None:
        profile = self._profiles.get_by_id(resident_profile_id)
        if profile is None:
            raise NotFoundError(detail="resident profile not found")
        if profile.organization_id != organization_id:
            raise ValueError("resident profile does not belong to this organization")

    def _check_bed(self, bed_id: UUID, organization_id: UUID) -> Bed:
        bed = self._beds.get_by_id(bed_id)
        if bed is None:
            raise NotFoundError(detail="bed not found")
        if bed.organization_id != organization_id:
            raise ValueError("bed does not belong to this organization")
        return bed

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
