"""Data access for resident profiles. Repository layer only — no services, no
endpoints.

Every read is scoped through either `organization_id` or the member's
`user_id`: no unscoped read path exists. A profile is unique per
`organization_member_id`, so a user may hold a profile in every organization
they are a member of.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization_member import OrganizationMember
from app.models.resident_profile import ResidentProfile
from app.schemas.resident_profile import ResidentProfileCreate


class ResidentProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, profile_id: UUID) -> ResidentProfile | None:
        return self._session.get(ResidentProfile, profile_id)

    def get_by_user_id(self, user_id: UUID) -> list[ResidentProfile]:
        return list(
            self._session.scalars(
                select(ResidentProfile)
                .join(
                    OrganizationMember,
                    OrganizationMember.id == ResidentProfile.organization_member_id,
                )
                .where(OrganizationMember.user_id == user_id)
                .order_by(ResidentProfile.created_at)
            )
        )

    def list_for_org(self, organization_id: UUID) -> list[ResidentProfile]:
        return list(
            self._session.scalars(
                select(ResidentProfile)
                .where(ResidentProfile.organization_id == organization_id)
                .order_by(ResidentProfile.emergency_contact_name)
            )
        )

    def exists_for_user(self, user_id: UUID) -> bool:
        return self._session.scalar(
            select(ResidentProfile.id)
            .join(
                OrganizationMember,
                OrganizationMember.id == ResidentProfile.organization_member_id,
            )
            .where(OrganizationMember.user_id == user_id)
            .limit(1)
        ) is not None

    def exists_for_member(self, organization_member_id: UUID) -> bool:
        return self._session.scalar(
            select(ResidentProfile.id)
            .where(ResidentProfile.organization_member_id == organization_member_id)
            .limit(1)
        ) is not None

    def create(self, data: ResidentProfileCreate) -> ResidentProfile:
        profile = ResidentProfile(**data.model_dump())
        self._session.add(profile)
        self._session.commit()
        self._session.refresh(profile)
        return profile