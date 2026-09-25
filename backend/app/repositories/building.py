"""Data access for buildings. Repository layer only — no services, no endpoints.

Every read is scoped by `organization_id`: no unscoped read path exists.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.building import Building
from app.schemas.building import BuildingCreate


class BuildingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, building_id: UUID) -> Building | None:
        return self._session.get(Building, building_id)

    def list_for_property(self, property_id: UUID) -> list[Building]:
        return list(
            self._session.scalars(
                select(Building)
                .where(Building.property_id == property_id)
                .order_by(Building.name)
            )
        )

    def exists_by_name(self, property_id: UUID, name: str) -> bool:
        return self._session.scalar(
            select(Building.id)
            .where(
                Building.property_id == property_id,
                Building.name == name,
            )
            .limit(1)
        ) is not None

    def create(self, data: BuildingCreate) -> Building:
        building = Building(**data.model_dump())
        self._session.add(building)
        self._session.commit()
        self._session.refresh(building)
        return building