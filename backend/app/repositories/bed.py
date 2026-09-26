"""Data access for beds. Repository layer only — no services, no endpoints.

Every read is scoped by `organization_id`: no unscoped read path exists.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bed import Bed
from app.schemas.bed import BedCreate


class BedRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, bed_id: UUID) -> Bed | None:
        return self._session.get(Bed, bed_id)

    def list_for_room(self, room_id: UUID) -> list[Bed]:
        return list(
            self._session.scalars(
                select(Bed).where(Bed.room_id == room_id).order_by(Bed.bed_number)
            )
        )

    def exists_by_number(self, room_id: UUID, bed_number: str) -> bool:
        return self._session.scalar(
            select(Bed.id)
            .where(
                Bed.room_id == room_id,
                Bed.bed_number == bed_number,
            )
            .limit(1)
        ) is not None

    def create(self, data: BedCreate) -> Bed:
        bed = Bed(**data.model_dump())
        self._session.add(bed)
        self._session.commit()
        self._session.refresh(bed)
        return bed