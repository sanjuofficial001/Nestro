"""Tests for the organization role enum and the Organization/OrganizationMember models."""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.enums import OrganizationRoleEnum, RoleEnum
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User


def test_org_role_enum_values() -> None:
    assert [role.value for role in OrganizationRoleEnum] == [
        "OWNER",
        "MANAGER",
        "STAFF",
    ]


def test_org_role_enum_is_str_enum() -> None:
    assert OrganizationRoleEnum("OWNER") is OrganizationRoleEnum.OWNER
    assert OrganizationRoleEnum.MANAGER.value == "MANAGER"


def test_organization_table_name() -> None:
    assert Organization.__tablename__ == "organizations"


def test_organization_primary_key_is_uuid() -> None:
    pk = Organization.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_organization_slug_unique_and_indexed() -> None:
    indexes = {idx.columns.keys()[0]: idx for idx in Organization.__table__.indexes}
    assert "slug" in indexes
    assert indexes["slug"].unique is True


def test_organization_timestamps_present() -> None:
    assert "created_at" in Organization.__table__.columns
    assert "updated_at" in Organization.__table__.columns


def test_organization_required_columns() -> None:
    nullable = {col.name for col in Organization.__table__.columns if col.nullable}
    assert "name" not in nullable
    assert "slug" not in nullable
    assert "is_active" not in nullable


def test_organization_member_table_name() -> None:
    assert OrganizationMember.__tablename__ == "organization_members"


def test_organization_member_primary_key_is_uuid() -> None:
    pk = OrganizationMember.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_organization_member_foreign_keys() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in OrganizationMember.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks
    assert ("user_id", "users") in fks


def test_organization_member_role_enum_type() -> None:
    role = OrganizationMember.__table__.c["role"]
    assert role.type.name == "organization_role"
    assert list(role.type.enums) == [r.value for r in OrganizationRoleEnum]


def test_organization_member_unique_membership() -> None:
    uniques = [
        constraint
        for constraint in OrganizationMember.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    columns = {tuple(c.name for c in u.columns) for u in uniques}
    assert ("organization_id", "user_id") in columns


def test_organization_member_timestamps_present() -> None:
    assert "created_at" in OrganizationMember.__table__.columns
    assert "updated_at" in OrganizationMember.__table__.columns


def test_bidirectional_relationships_compile() -> None:
    configure_mappers()
    org = Organization(name="ABC Mall", slug="abc-mall")
    user = User(email="a@example.com", full_name="Owner", role=RoleEnum.PG_OWNER)
    member = OrganizationMember(
        organization=org, user=user, role=OrganizationRoleEnum.OWNER
    )
    assert member in org.members
    assert member.organization is org
    assert member.user is user
    assert member in user.members