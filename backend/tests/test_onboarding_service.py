"""Tests for the onboarding service flow."""

import pytest

from app.models.enums import OrganizationRoleEnum, RoleEnum
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.user import UserRepository
from app.schemas.onboarding import OnboardingRequest
from app.schemas.user import UserCreate
from app.services.onboarding_service import OnboardingService


def seed_user(db_session, *, email: str = "owner@example.com", phone: str | None = None):
    return UserRepository(db_session).create(
        UserCreate(email=email, phone=phone, full_name="Owner", role=RoleEnum.PG_OWNER)
    )


def payload(**overrides) -> OnboardingRequest:
    values = {"organization_name": "My PG", "organization_slug": "my-pg"}
    values.update(overrides)
    return OnboardingRequest(**values)


def test_onboard_creates_organization_and_owner_membership(db_session) -> None:
    user = seed_user(db_session)
    organization, member = OnboardingService(db_session).onboard_user(user, payload())
    assert organization.id is not None
    assert organization.name == "My PG"
    assert organization.slug == "my-pg"
    assert organization.is_active is True
    assert member.id is not None
    assert member.organization_id == organization.id
    assert member.user_id == user.id
    assert member.role is OrganizationRoleEnum.OWNER


def test_onboard_duplicate_slug_raises(db_session) -> None:
    first = seed_user(db_session, email="first@example.com")
    second = seed_user(db_session, email="second@example.com")
    OnboardingService(db_session).onboard_user(first, payload())
    with pytest.raises(ValueError, match="organization slug already exists"):
        OnboardingService(db_session).onboard_user(second, payload())


def test_onboard_existing_membership_raises(db_session) -> None:
    user = seed_user(db_session)
    OnboardingService(db_session).onboard_user(user, payload())
    with pytest.raises(ValueError, match="user already onboarded"):
        OnboardingService(db_session).onboard_user(user, payload(organization_slug="other-pg"))


def test_onboard_failure_rolls_back_no_partial_organization(db_session, monkeypatch) -> None:
    user = seed_user(db_session)

    def boom(*_args, **_kwargs):
        raise RuntimeError("member creation failed")

    monkeypatch.setattr(
        "app.services.onboarding_service.OrganizationMember",
        type("BoomOrganizationMember", (), {"__init__": boom}),
    )
    with pytest.raises(RuntimeError):
        OnboardingService(db_session).onboard_user(user, payload())

    assert OrganizationRepository(db_session).get_by_slug("my-pg") is None
    assert OrganizationMemberRepository(db_session).get_for_user(user.id) == []