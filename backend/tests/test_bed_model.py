"""Tests for the Bed model metadata, enums, and relationships."""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.bed import Bed
from app.models.enums import BedStatusEnum
from app.models.room import Room


def test_bed_status_enum_values() -> None:
    assert [s.value for s in BedStatusEnum] == [
        "AVAILABLE",
        "OCCUPIED",
        "BLOCKED",
        "MAINTENANCE",
    ]


def test_bed_table_name() -> None:
    assert Bed.__tablename__ == "beds"


def test_bed_primary_key_is_uuid() -> None:
    pk = Bed.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_bed_foreign_keys() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in Bed.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks
    assert ("room_id", "rooms") in fks


def test_bed_required_columns() -> None:
    nullable = {col.name for col in Bed.__table__.columns if col.nullable}
    assert "organization_id" not in nullable
    assert "room_id" not in nullable
    assert "bed_number" not in nullable
    assert "status" not in nullable


def test_bed_status_default_is_available() -> None:
    assert Bed.__table__.c["status"].default.arg is BedStatusEnum.AVAILABLE


def test_bed_enum_column_type() -> None:
    column = Bed.__table__.c["status"]
    assert column.type.name == "bed_status"
    assert list(column.type.enums) == [s.value for s in BedStatusEnum]


def test_bed_indexes() -> None:
    indexed = {idx.columns.keys()[0] for idx in Bed.__table__.indexes}
    assert "organization_id" in indexed
    assert "room_id" in indexed
    assert "status" in indexed


def test_bed_unique_room_number() -> None:
    uniques = {
        tuple(c.columns.keys())
        for c in Bed.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("room_id", "bed_number") in uniques


def test_bed_timestamps() -> None:
    assert "created_at" in Bed.__table__.columns
    assert "updated_at" in Bed.__table__.columns


def test_room_beds_relationship_compiles() -> None:
    configure_mappers()
    room = Room(floor=None, room_number="A101", room_type="SINGLE")
    bed = Bed(room=room, bed_number="1")
    assert bed.room is room
    assert bed in room.beds