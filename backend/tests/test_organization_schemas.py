"""Tests for organization and membership schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import OrganizationRoleEnum
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.schemas.organization import OrganizationCreate, OrganizationRead
from app.schemas.organization_member import (
    OrganizationMemberCreate,
    OrganizationMemberRead,
)


def test_organization_create_valid() -> None:
    data = OrganizationCreate(name="ABC Mall", slug="abc-mall")
    assert data.name == "ABC Mall"
    assert data.slug == "abc-mall"


def test_organization_create_strips_name() -> None:
    data = OrganizationCreate(name="  ABC Mall  ", slug="abc-mall")
    assert data.name == "ABC Mall"


@pytest.mark.parametrize(
    "slug",
    [
        "AB",
        "UPPERCASE",
        "spaces allowed",
        "  leading-space",
        "trailing-space ",
    ],
)
def test_organization_create_rejects_invalid_slug(slug: str) -> None:
    with pytest.raises(ValidationError):
        OrganizationCreate(name="ABC Mall", slug=slug)


def test_organization_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        OrganizationCreate(name="ABC Mall", slug="abc-mall", is_active=False)


def test_organization_read_from_attributes() -> None:
    now = datetime.now(UTC)
    org = Organization(
        id=uuid4(),
        name="ABC Mall",
        slug="abc-mall",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    read = OrganizationRead.model_validate(org)
    assert read.id == org.id
    assert read.name == "ABC Mall"
    assert read.slug == "abc-mall"
    assert read.is_active is True
    assert read.created_at == now


def test_organization_member_create_valid() -> None:
    org_id = uuid4()
    user_id = uuid4()
    data = OrganizationMemberCreate(
        organization_id=org_id,
        user_id=user_id,
        role=OrganizationRoleEnum.MANAGER,
    )
    assert data.organization_id == org_id
    assert data.user_id == user_id
    assert data.role is OrganizationRoleEnum.MANAGER


def test_organization_member_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        OrganizationMemberCreate(
            organization_id=uuid4(),
            user_id=uuid4(),
            role=OrganizationRoleEnum.STAFF,
            joined_at=datetime.now(UTC),
        )


def test_organization_member_read_from_attributes() -> None:
    now = datetime.now(UTC)
    member = OrganizationMember(
        id=uuid4(),
        organization_id=uuid4(),
        user_id=uuid4(),
        role=OrganizationRoleEnum.OWNER,
        created_at=now,
        updated_at=now,
    )
    read = OrganizationMemberRead.model_validate(member)
    assert read.id == member.id
    assert read.organization_id == member.organization_id
    assert read.user_id == member.user_id
    assert read.role is OrganizationRoleEnum.OWNER
    assert read.created_at == now