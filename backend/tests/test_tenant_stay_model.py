"""Tests for the TenantStay model metadata and its relationships."""

from datetime import date

from sqlalchemy import Date, ForeignKeyConstraint, Index, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.bed import Bed
from app.models.building import Building
from app.models.enums import (
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
    RoomTypeEnum,
    TenantStayStatusEnum,
)
from app.models.floor import Floor
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.property import Property
from app.models.resident_profile import ResidentProfile
from app.models.room import Room
from app.models.tenant_stay import TenantStay
from app.models.user import User


def test_tenant_stay_table_name() -> None:
    assert TenantStay.__tablename__ == "tenant_stays"


def test_tenant_stay_primary_key_is_uuid() -> None:
    pk = TenantStay.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_tenant_stay_foreign_keys() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in TenantStay.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks
    assert ("resident_profile_id", "resident_profiles") in fks
    assert ("property_id", "properties") in fks
    assert ("bed_id", "beds") in fks


def test_tenant_stay_required_and_nullable_columns() -> None:
    nullable = {col.name for col in TenantStay.__table__.columns if col.nullable}
    assert "organization_id" not in nullable
    assert "resident_profile_id" not in nullable
    assert "property_id" not in nullable
    assert "bed_id" not in nullable
    assert "start_date" not in nullable
    assert "status" not in nullable
    assert "end_date" in nullable
    assert "notes" in nullable


def test_tenant_stay_start_date_is_date_type() -> None:
    assert isinstance(TenantStay.__table__.c["start_date"].type, Date)
    assert isinstance(TenantStay.__table__.c["end_date"].type, Date)


def test_tenant_stay_status_enum_values() -> None:
    status = TenantStay.__table__.c["status"]
    assert set(status.type.enums) == {"ACTIVE", "COMPLETED", "CANCELLED"}
    assert {s.value for s in TenantStayStatusEnum} == {"ACTIVE", "COMPLETED", "CANCELLED"}


def test_tenant_stay_indexes() -> None:
    indexed = {idx.columns.keys()[0] for idx in TenantStay.__table__.indexes}
    assert "organization_id" in indexed
    assert "resident_profile_id" in indexed
    assert "bed_id" in indexed


def test_tenant_stay_active_bed_partial_unique_index() -> None:
    index = next(
        i for i in TenantStay.__table__.indexes if i.name == "uq_tenant_stays_active_bed"
    )
    assert isinstance(index, Index)
    assert index.unique is True
    assert index.columns.keys() == ["bed_id"]
    assert "status = 'ACTIVE'" in str(index.dialect_options["sqlite"]["where"])
    assert "status = 'ACTIVE'" in str(index.dialect_options["postgresql"]["where"])


def test_tenant_stay_timestamps() -> None:
    assert "created_at" in TenantStay.__table__.columns
    assert "updated_at" in TenantStay.__table__.columns


def test_tenant_stay_relationships_compile() -> None:
    configure_mappers()
    org = Organization(name="ABC Mall", slug="abc-mall")
    user = User(email="alice@example.com", full_name="Alice", role=RoleEnum.TENANT)
    member = OrganizationMember(
        organization=org, user=user, role=OrganizationRoleEnum.STAFF
    )
    prop = Property(
        organization=org, name="PSG Boys PG", property_type=PropertyTypeEnum.PG
    )
    building = Building(property=prop, name="Block A")
    floor = Floor(building=building, floor_number=1, name="First")
    room = Room(floor=floor, room_number="101", room_type=RoomTypeEnum.SINGLE)
    bed = Bed(room=room, bed_number="1")
    profile = ResidentProfile(
        organization=org,
        organization_member=member,
        emergency_contact_name="Bob",
        emergency_contact_phone="9999999999",
        address="12 Main St",
        property=prop,
    )
    stay = TenantStay(
        organization=org,
        resident_profile=profile,
        property=prop,
        bed=bed,
        start_date=date(2026, 1, 1),
        status=TenantStayStatusEnum.ACTIVE,
    )
    assert stay.organization is org
    assert stay in org.tenant_stays
    assert stay.resident_profile is profile
    assert stay in profile.tenant_stays
    assert stay.property is prop
    assert stay in prop.tenant_stays
    assert stay.bed is bed
    assert stay in bed.tenant_stays
    assert bed in room.beds
    assert room in floor.rooms
    assert floor in building.floors
    assert building in prop.buildings