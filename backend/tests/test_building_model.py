"""Tests for the Building model metadata and its bidirectional relationships."""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.building import Building
from app.models.enums import PropertyTypeEnum
from app.models.property import Property


def test_building_table_name() -> None:
    assert Building.__tablename__ == "buildings"


def test_building_primary_key_is_uuid() -> None:
    pk = Building.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_building_foreign_keys() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in Building.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks
    assert ("property_id", "properties") in fks


def test_building_required_columns() -> None:
    nullable = {col.name for col in Building.__table__.columns if col.nullable}
    assert "organization_id" not in nullable
    assert "property_id" not in nullable
    assert "name" not in nullable
    assert "description" in nullable


def test_building_indexes() -> None:
    indexed = {idx.columns.keys()[0] for idx in Building.__table__.indexes}
    assert "organization_id" in indexed
    assert "property_id" in indexed


def test_building_unique_property_name() -> None:
    uniques = {
        tuple(c.columns.keys())
        for c in Building.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("property_id", "name") in uniques


def test_building_timestamps() -> None:
    assert "created_at" in Building.__table__.columns
    assert "updated_at" in Building.__table__.columns


def test_property_buildings_relationship_compiles() -> None:
    configure_mappers()
    prop = Property(name="PSG Boys PG", property_type=PropertyTypeEnum.PG)
    building = Building(name="Block A", property=prop)
    assert building.property is prop
    assert building in prop.buildings