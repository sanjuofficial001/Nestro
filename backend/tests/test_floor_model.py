"""Tests for the Floor model metadata and its bidirectional relationships."""

from sqlalchemy import ForeignKeyConstraint, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.building import Building
from app.models.floor import Floor
from app.models.property import Property


def test_floor_table_name() -> None:
    assert Floor.__tablename__ == "floors"


def test_floor_primary_key_is_uuid() -> None:
    pk = Floor.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_floor_foreign_keys() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in Floor.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks
    assert ("building_id", "buildings") in fks


def test_floor_required_columns() -> None:
    nullable = {col.name for col in Floor.__table__.columns if col.nullable}
    assert "organization_id" not in nullable
    assert "building_id" not in nullable
    assert "name" not in nullable
    assert "floor_number" not in nullable
    assert isinstance(Floor.__table__.c["floor_number"].type, Integer)


def test_floor_indexes() -> None:
    indexed = {idx.columns.keys()[0] for idx in Floor.__table__.indexes}
    assert "organization_id" in indexed
    assert "building_id" in indexed


def test_floor_unique_building_number() -> None:
    uniques = {
        tuple(c.columns.keys())
        for c in Floor.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("building_id", "floor_number") in uniques


def test_floor_timestamps() -> None:
    assert "created_at" in Floor.__table__.columns
    assert "updated_at" in Floor.__table__.columns


def test_building_floors_relationship_compiles() -> None:
    configure_mappers()
    prop = Property(name="PSG Boys PG", property_type="PG")
    building = Building(name="Block A", property=prop)
    floor = Floor(building=building, floor_number=1, name="First Floor")
    assert floor.building is building
    assert floor in building.floors