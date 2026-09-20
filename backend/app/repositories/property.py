"""Data access for properties. Repository layer only — no services, no endpoints.

Every read is scoped by `organization_id`: no unscoped read path exists.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property import Property
from app.schemas.property import PropertyCreate


class PropertyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, property_id: UUID) -> Property | None:
        return self._session.get(Property, property_id)

    def list_for_org(self, organization_id: UUID) -> list[Property]:
        return list(
            self._session.scalars(
                select(Property)
                .where(Property.organization_id == organization_id)
                .order_by(Property.name)
            )
        )

    def exists_by_name(self, organization_id: UUID, name: str) -> bool:
        return self._session.scalar(
            select(Property.id)
            .where(
                Property.organization_id == organization_id,
                Property.name == name,
            )
            .limit(1)
        ) is not None

    def create(self, data: PropertyCreate) -> Property:
        property = Property(**data.model_dump())
        self._session.add(property)
        self._session.commit()
        self._session.refresh(property)
        return property