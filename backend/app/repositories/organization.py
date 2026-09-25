"""Data access for organizations. Repository layer only — no services, no endpoints."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, organization_id: UUID) -> Organization | None:
        return self._session.get(Organization, organization_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self._session.scalar(
            select(Organization).where(Organization.slug == slug)
        )

    def exists_by_slug(self, slug: str) -> bool:
        return self._session.scalar(
            select(Organization.id).where(Organization.slug == slug).limit(1)
        ) is not None

    def exists_by_name(self, name: str) -> bool:
        normalized = name.strip().lower()
        return self._session.scalar(
            select(Organization.id)
            .where(func.lower(Organization.name) == normalized)
            .limit(1)
        ) is not None

    def create(self, data: OrganizationCreate) -> Organization:
        organization = Organization(**data.model_dump())
        self._session.add(organization)
        self._session.commit()
        self._session.refresh(organization)
        return organization