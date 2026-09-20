"""Tests for the property enums and the Property model metadata."""

from sqlalchemy import ForeignKeyConstraint, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.enums import PropertyStatusEnum, PropertyTypeEnum
from app.models.organization import Organization
from app.models.property import Property


def test_property_type_enum_values() -> None:
    assert [t.value for t in PropertyTypeEnum] == [
        "PG",
        "HOSTEL",
        "HOTEL",
        "APARTMENT",
        "COLIVING",
    ]


def test_property_status_enum_values() -> None:
    assert [s.value for s in PropertyStatusEnum] == [
        "ACTIVE",
        "INACTIVE",
        "CLOSED",
    ]


def test_property_type_is_str_enum() -> None:
    assert PropertyTypeEnum("PG") is PropertyTypeEnum.PG
    assert PropertyStatusEnum("CLOSED").value == "CLOSED"


def test_property_table_name() -> None:
    assert Property.__tablename__ == "properties"


def test_property_primary_key_is_uuid() -> None:
    pk = Property.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_property_foreign_key_to_organizations() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in Property.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks


def test_property_enum_column_types() -> None:
    ptype = Property.__table__.c["property_type"]
    assert ptype.type.name == "property_type"
    assert list(ptype.type.enums) == [t.value for t in PropertyTypeEnum]
    pstatus = Property.__table__.c["status"]
    assert pstatus.type.name == "property_status"
    assert list(pstatus.type.enums) == [s.value for s in PropertyStatusEnum]


def test_property_required_columns() -> None:
    nullable = {col.name for col in Property.__table__.columns if col.nullable}
    assert "organization_id" not in nullable
    assert "name" not in nullable
    assert "property_type" not in nullable
    assert "status" not in nullable
    assert "address" in nullable
    assert "contact_phone" in nullable
    assert "rules" in nullable


def test_property_indexes() -> None:
    indexed = {idx.columns.keys()[0] for idx in Property.__table__.indexes}
    assert "organization_id" in indexed
    assert "property_type" in indexed
    assert "status" in indexed


def test_property_soft_delete_and_timestamps() -> None:
    assert "deleted_at" in Property.__table__.columns
    assert "created_at" in Property.__table__.columns
    assert "updated_at" in Property.__table__.columns


def test_organization_properties_relationship_compiles() -> None:
    configure_mappers()
    org = Organization(name="ABC Mall", slug="abc-mall")
    property = Property(
        organization=org,
        name="Sunrise Apartments",
        property_type=PropertyTypeEnum.PG,
    )
    assert property.organization is org
    assert property in org.properties