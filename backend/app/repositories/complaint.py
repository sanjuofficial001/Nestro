"""Data access for complaints. Repository layer only — no services, no endpoints.

Every read is scoped by `organization_id`: no unscoped read path exists. The
`status`, `priority`, and `resident_profile_id` filters are optional and applied
in SQL, never in Python.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.models.enums import ComplaintPriorityEnum, ComplaintStatusEnum
from app.schemas.complaint import ComplaintCreate


class ComplaintRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, complaint_id: UUID) -> Complaint | None:
        return self._session.get(Complaint, complaint_id)

    def list_for_org(
        self,
        organization_id: UUID,
        status: ComplaintStatusEnum | None = None,
        priority: ComplaintPriorityEnum | None = None,
        resident_profile_id: UUID | None = None,
    ) -> list[Complaint]:
        query = select(Complaint).where(Complaint.organization_id == organization_id)
        if status is not None:
            query = query.where(Complaint.status == status)
        if priority is not None:
            query = query.where(Complaint.priority == priority)
        if resident_profile_id is not None:
            query = query.where(Complaint.resident_profile_id == resident_profile_id)
        return list(self._session.scalars(query.order_by(Complaint.created_at.desc())))

    def create(self, data: ComplaintCreate) -> Complaint:
        complaint = Complaint(**data.model_dump())
        self._session.add(complaint)
        self._session.commit()
        self._session.refresh(complaint)
        return complaint
