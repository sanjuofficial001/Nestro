"""Organization onboarding business logic.

`OnboardingService.onboard_user` bootstraps a user's first organization with an
OWNER membership. It never joins existing organizations, never creates
properties, and runs once per user: any later call is rejected. The create
steps share one transaction — a failure rolls back so no partial organization
is ever persisted.
"""

from sqlalchemy.orm import Session

from app.models.enums import OrganizationRoleEnum
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.schemas.onboarding import OnboardingRequest


class OnboardingService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def onboard_user(
        self,
        user: User,
        payload: OnboardingRequest,
    ) -> tuple[Organization, OrganizationMember]:
        if not user.is_active:
            raise ValueError("user is not active")

        organization_repo = OrganizationRepository(self._session)
        if organization_repo.exists_by_slug(payload.organization_slug):
            raise ValueError("organization slug already exists")

        member_repo = OrganizationMemberRepository(self._session)
        if member_repo.get_for_user(user.id):
            raise ValueError("user already onboarded")

        organization = Organization(
            name=payload.organization_name,
            slug=payload.organization_slug,
            is_active=True,
        )
        self._session.add(organization)
        try:
            self._session.flush()
            member = OrganizationMember(
                user_id=user.id,
                organization_id=organization.id,
                role=OrganizationRoleEnum.OWNER,
            )
            self._session.add(member)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return organization, member