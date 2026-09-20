"""Tests for the organization and membership repositories on SQLite."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import OrganizationRoleEnum
from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate


def create_org(repo: OrganizationRepository, *, slug: str = "abc-mall") -> Organization:
    return repo.create(OrganizationCreate(name="ABC Mall", slug=slug))


def test_create_organization(db_session) -> None:
    org = create_org(OrganizationRepository(db_session))
    assert org.id is not None
    assert org.name == "ABC Mall"
    assert org.slug == "abc-mall"
    assert org.is_active is True
    assert org.created_at is not None


def test_exists_by_slug(db_session) -> None:
    repo = OrganizationRepository(db_session)
    assert repo.exists_by_slug("abc-mall") is False
    create_org(repo)
    assert repo.exists_by_slug("abc-mall") is True


def test_get_by_slug(db_session) -> None:
    repo = OrganizationRepository(db_session)
    org = create_org(repo, slug="sunrise-apartments")
    fetched = repo.get_by_slug("sunrise-apartments")
    assert fetched is not None
    assert fetched.id == org.id
    assert repo.get_by_slug("missing") is None


def test_create_membership(db_session) -> None:
    org = create_org(OrganizationRepository(db_session))
    member = OrganizationMemberRepository(db_session).create(
        OrganizationMemberCreate(
            organization_id=org.id,
            user_id=uuid4(),
            role=OrganizationRoleEnum.OWNER,
        )
    )
    assert member.id is not None
    assert member.role is OrganizationRoleEnum.OWNER


def test_duplicate_membership_blocked(db_session) -> None:
    org = create_org(OrganizationRepository(db_session))
    user_id = uuid4()
    member_repo = OrganizationMemberRepository(db_session)
    member_repo.create(
        OrganizationMemberCreate(
            organization_id=org.id,
            user_id=user_id,
            role=OrganizationRoleEnum.STAFF,
        )
    )
    with pytest.raises(IntegrityError):
        member_repo.create(
            OrganizationMemberCreate(
                organization_id=org.id,
                user_id=user_id,
                role=OrganizationRoleEnum.MANAGER,
            )
        )


def test_get_members_for_org_and_get_org_for_user(db_session) -> None:
    org = create_org(OrganizationRepository(db_session))
    user_id = uuid4()
    member_repo = OrganizationMemberRepository(db_session)
    member = member_repo.create(
        OrganizationMemberCreate(
            organization_id=org.id,
            user_id=user_id,
            role=OrganizationRoleEnum.OWNER,
        )
    )
    members = member_repo.get_members_for_org(org.id)
    assert len(members) == 1
    assert members[0].id == member.id
    assert member_repo.get_org_for_user(user_id).id == member.id
    assert member_repo.get_org_for_user(uuid4()) is None


def test_exists_membership(db_session) -> None:
    org = create_org(OrganizationRepository(db_session))
    user_id = uuid4()
    member_repo = OrganizationMemberRepository(db_session)
    assert member_repo.exists_membership(org.id, user_id) is False
    member_repo.create(
        OrganizationMemberCreate(
            organization_id=org.id,
            user_id=user_id,
            role=OrganizationRoleEnum.MANAGER,
        )
    )
    assert member_repo.exists_membership(org.id, user_id) is True