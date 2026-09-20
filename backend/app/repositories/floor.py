"""Data access for floors. Repository layer only — no services, no endpoints.

Every read is scoped by `organization_id`: no unscoped read path exists.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.floor import Floor
from app.schemas.floor import FloorCreate


class FloorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, floor_id: UUID) -> Floor | None:
        return self._session.get(Floor, floor_id)

    def list_for_building(self, building_id: UUID) -> list[Floor]:
        return list(
            self._session.scalars(
                select(Floor)
                .where(Floor.building_id == building_id)
                .order_by(Floor.floor_number)
            )
        )

    def create(self, data: FloorCreate) -> Floor:
        floor = Floor(**data.model_dump())
        self._session.add(floor)
        self._session.commit()
        self._session.refresh(floor)
        return floor