"""Data access for tenant stays. Repository layer only — no services, no
endpoints.

Reads are keyed by stay id or scoped by organization / resident / bed. The
`uq_tenant_stays_active_bed` partial unique index (bed + status = ACTIVE) is
the database-level guarantee that a bed has at most one open stay; the
repository surfaces it as `get_active_for_bed`.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TenantStayStatusEnum
from app.models.tenant_stay import TenantStay
from app.schemas.tenant_stay import TenantStayCreate


class TenantStayRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, stay_id: UUID) -> TenantStay | None:
        return self._session.get(TenantStay, stay_id)

    def list_for_org(self, organization_id: UUID) -> list[TenantStay]:
        return list(
            self._session.scalars(
                select(TenantStay)
                .where(TenantStay.organization_id == organization_id)
                .order_by(TenantStay.start_date.desc())
            )
        )

    def list_for_resident(self, resident_profile_id: UUID) -> list[TenantStay]:
        return list(
            self._session.scalars(
                select(TenantStay)
                .where(TenantStay.resident_profile_id == resident_profile_id)
                .order_by(TenantStay.start_date.desc())
            )
        )

    def list_for_bed(self, bed_id: UUID) -> list[TenantStay]:
        return list(
            self._session.scalars(
                select(TenantStay)
                .where(TenantStay.bed_id == bed_id)
                .order_by(TenantStay.start_date.desc())
            )
        )

    def get_active_for_bed(self, bed_id: UUID) -> TenantStay | None:
        return self._session.scalar(
            select(TenantStay)
            .where(
                TenantStay.bed_id == bed_id,
                TenantStay.status == TenantStayStatusEnum.ACTIVE,
            )
            .limit(1)
        )

    def create(self, data: TenantStayCreate) -> TenantStay:
        stay = TenantStay(**data.model_dump())
        self._session.add(stay)
        self._session.commit()
        self._session.refresh(stay)
        return stay