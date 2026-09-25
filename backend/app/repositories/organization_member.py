"""Data access for organization memberships. Repository layer only."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization_member import OrganizationMember
from app.schemas.organization_member import OrganizationMemberCreate


class OrganizationMemberRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, member_id: UUID) -> OrganizationMember | None:
        return self._session.get(OrganizationMember, member_id)

    def get_members_for_org(self, organization_id: UUID) -> list[OrganizationMember]:
        return list(
            self._session.scalars(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == organization_id
                )
            )
        )

    def get_org_for_user(self, user_id: UUID) -> OrganizationMember | None:
        return self._session.scalar(
            select(OrganizationMember).where(OrganizationMember.user_id == user_id)
        )

    def get_for_user(self, user_id: UUID) -> list[OrganizationMember]:
        return list(
            self._session.scalars(
                select(OrganizationMember).where(OrganizationMember.user_id == user_id)
            )
        )

    def exists_membership(self, organization_id: UUID, user_id: UUID) -> bool:
        return self._session.scalar(
            select(OrganizationMember.id)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
            .limit(1)
        ) is not None

    def create(self, data: OrganizationMemberCreate) -> OrganizationMember:
        member = OrganizationMember(**data.model_dump())
        self._session.add(member)
        self._session.commit()
        self._session.refresh(member)
        return member