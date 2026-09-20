"""Tests for the resident profile repository on SQLite, verifying org and user scoping."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import OrganizationRoleEnum, PropertyTypeEnum, RoleEnum
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.property import Property
from app.models.resident_profile import ResidentProfile
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.user import UserRepository
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.user import UserCreate


def create_org(repo: OrganizationRepository, *, slug: str) -> Organization:
    return repo.create(OrganizationCreate(name=slug.title(), slug=slug))


def create_user(repo: UserRepository, *, email: str) -> User:
    return repo.create(
        UserCreate(email=email, phone=None, full_name="Test User", role=RoleEnum.TENANT)
    )


def create_member(
    repo: OrganizationMemberRepository, org: Organization, user: User
) -> OrganizationMember:
    return repo.create(
        OrganizationMemberCreate(
            organization_id=org.id,
            user_id=user.id,
            role=OrganizationRoleEnum.STAFF,
        )
    )


def create_property(
    repo: PropertyRepository,
    org: Organization,
    *,
    name: str,
) -> Property:
    return repo.create(
        PropertyCreate(name=name, property_type=PropertyTypeEnum.PG, organization_id=org.id)
    )


def create_profile(
    repo: ResidentProfileRepository,
    org: Organization,
    member: OrganizationMember,
    *,
    property_id=None,
    contact: str = "Bob",
) -> ResidentProfile:
    return repo.create(
        ResidentProfileCreate(
            organization_id=org.id,
            organization_member_id=member.id,
            property_id=property_id,
            emergency_contact_name=contact,
            emergency_contact_phone="9999999999",
            address="12 Main St",
        )
    )


def seed(db_session):
    """One org, one user, one member, one profile."""
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    user = create_user(UserRepository(db_session), email="alice@example.com")
    member = create_member(OrganizationMemberRepository(db_session), org, user)
    profile = create_profile(ResidentProfileRepository(db_session), org, member)
    return org, user, member, profile


def test_create_profile(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    user = create_user(UserRepository(db_session), email="alice@example.com")
    member = create_member(OrganizationMemberRepository(db_session), org, user)
    prop = create_property(PropertyRepository(db_session), org, name="PSG Boys PG")

    profile = create_profile(
        ResidentProfileRepository(db_session),
        org,
        member,
        property_id=prop.id,
        contact="Bob",
    )
    assert profile.id is not None
    assert profile.organization_id == org.id
    assert profile.organization_member_id == member.id
    assert profile.property_id == prop.id
    assert profile.is_active is True
    assert profile.created_at is not None


def test_get_by_id(db_session) -> None:
    _, _, _, profile = seed(db_session)
    fetched = ResidentProfileRepository(db_session).get_by_id(profile.id)
    assert fetched is not None
    assert fetched.id == profile.id
    assert fetched.emergency_contact_name == "Bob"


def test_get_by_user_id_across_orgs(db_session) -> None:
    org_repo = OrganizationRepository(db_session)
    org_a = create_org(org_repo, slug="abc-mall")
    org_b = create_org(org_repo, slug="sunrise")
    user = create_user(UserRepository(db_session), email="alice@example.com")

    member_repo = OrganizationMemberRepository(db_session)
    member_a = create_member(member_repo, org_a, user)
    member_b = create_member(member_repo, org_b, user)

    profile_repo = ResidentProfileRepository(db_session)
    profile_a = create_profile(profile_repo, org_a, member_a, contact="Bob")
    profile_b = create_profile(profile_repo, org_b, member_b, contact="Carol")

    found = {p.id for p in profile_repo.get_by_user_id(user.id)}
    assert found == {profile_a.id, profile_b.id}


def test_get_by_user_id_empty(db_session) -> None:
    assert ResidentProfileRepository(db_session).get_by_user_id(uuid4()) == []


def test_list_for_org_is_scoped_and_ordered(db_session) -> None:
    org_repo = OrganizationRepository(db_session)
    org_a = create_org(org_repo, slug="abc-mall")
    org_b = create_org(org_repo, slug="sunrise")
    user_repo = UserRepository(db_session)
    user_a = create_user(user_repo, email="a@example.com")
    user_b = create_user(user_repo, email="b@example.com")
    user_c = create_user(user_repo, email="c@example.com")

    member_repo = OrganizationMemberRepository(db_session)
    member_a = create_member(member_repo, org_a, user_a)
    member_b = create_member(member_repo, org_a, user_b)
    member_c = create_member(member_repo, org_b, user_c)

    profile_repo = ResidentProfileRepository(db_session)
    create_profile(profile_repo, org_a, member_a, contact="Zoe")
    create_profile(profile_repo, org_a, member_b, contact="Amy")
    create_profile(profile_repo, org_b, member_c, contact="Carol")

    contacts_a = [p.emergency_contact_name for p in profile_repo.list_for_org(org_a.id)]
    assert contacts_a == ["Amy", "Zoe"]
    contacts_b = [p.emergency_contact_name for p in profile_repo.list_for_org(org_b.id)]
    assert contacts_b == ["Carol"]


def test_exists_for_user(db_session) -> None:
    org_a = create_org(OrganizationRepository(db_session), slug="abc-mall")
    user = create_user(UserRepository(db_session), email="alice@example.com")
    other = create_user(UserRepository(db_session), email="other@example.com")
    member = create_member(OrganizationMemberRepository(db_session), org_a, user)
    create_profile(ResidentProfileRepository(db_session), org_a, member)

    assert ResidentProfileRepository(db_session).exists_for_user(user.id) is True
    assert ResidentProfileRepository(db_session).exists_for_user(other.id) is False


def test_unique_member_enforced(db_session) -> None:
    org = create_org(OrganizationRepository(db_session), slug="abc-mall")
    user = create_user(UserRepository(db_session), email="alice@example.com")
    member = create_member(OrganizationMemberRepository(db_session), org, user)
    repo = ResidentProfileRepository(db_session)
    create_profile(repo, org, member)

    with pytest.raises(IntegrityError):
        create_profile(repo, org, member, contact="Dup")
    db_session.rollback()