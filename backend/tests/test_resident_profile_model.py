"""Tests for the ResidentProfile model metadata and its relationships."""

from sqlalchemy import Boolean, ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.enums import OrganizationRoleEnum, RoleEnum
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.resident_profile import ResidentProfile
from app.models.user import User


def test_resident_profile_table_name() -> None:
    assert ResidentProfile.__tablename__ == "resident_profiles"


def test_resident_profile_primary_key_is_uuid() -> None:
    pk = ResidentProfile.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_resident_profile_foreign_keys() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in ResidentProfile.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks
    assert ("organization_member_id", "organization_members") in fks
    assert ("property_id", "properties") in fks


def test_resident_profile_unique_member() -> None:
    uniques = {
        tuple(c.columns.keys())
        for c in ResidentProfile.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("organization_member_id",) in uniques


def test_resident_profile_required_columns() -> None:
    nullable = {col.name for col in ResidentProfile.__table__.columns if col.nullable}
    assert "organization_id" not in nullable
    assert "organization_member_id" not in nullable
    assert "emergency_contact_name" not in nullable
    assert "emergency_contact_phone" not in nullable
    assert "address" not in nullable
    assert "is_active" not in nullable
    assert "property_id" in nullable
    assert "notes" in nullable


def test_resident_profile_active_default() -> None:
    default = ResidentProfile.__table__.c["is_active"].default
    assert default.arg is True
    assert isinstance(ResidentProfile.__table__.c["is_active"].type, Boolean)


def test_resident_profile_indexes() -> None:
    indexed = {idx.columns.keys()[0] for idx in ResidentProfile.__table__.indexes}
    assert "organization_id" in indexed
    assert "property_id" in indexed


def test_resident_profile_timestamps() -> None:
    assert "created_at" in ResidentProfile.__table__.columns
    assert "updated_at" in ResidentProfile.__table__.columns


def test_resident_profile_relationships_compile() -> None:
    configure_mappers()
    org = Organization(name="ABC Mall", slug="abc-mall")
    user = User(
        email="alice@example.com",
        full_name="Alice",
        role=RoleEnum.TENANT,
    )
    member = OrganizationMember(
        organization=org, user=user, role=OrganizationRoleEnum.STAFF
    )
    profile = ResidentProfile(
        organization=org,
        organization_member=member,
        emergency_contact_name="Bob",
        emergency_contact_phone="9999999999",
        address="12 Main St",
    )
    assert profile.organization is org
    assert profile in org.resident_profiles
    assert profile.organization_member is member
    assert member.resident_profile is profile
    assert member.user is user
    assert member in user.members