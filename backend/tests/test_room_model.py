"""Tests for the Room model metadata, enums, and relationships.

Room capacity is a derived value (COUNT of its beds); the model asserts no
capacity-like column ever exists on `rooms`.
"""

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, Uuid
from sqlalchemy.orm import configure_mappers

from app.models.bed import Bed
from app.models.enums import RoomTypeEnum
from app.models.floor import Floor
from app.models.room import Room


def test_room_type_enum_values() -> None:
    assert [t.value for t in RoomTypeEnum] == [
        "SINGLE",
        "DOUBLE",
        "TRIPLE",
        "FOUR_SHARE",
        "FIVE_SHARE",
        "CUSTOM",
    ]


def test_room_table_name() -> None:
    assert Room.__tablename__ == "rooms"


def test_room_primary_key_is_uuid() -> None:
    pk = Room.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_room_foreign_keys() -> None:
    fks = {
        (constraint.columns.values()[0].name, constraint.referred_table.name)
        for constraint in Room.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert ("organization_id", "organizations") in fks
    assert ("floor_id", "floors") in fks


def test_room_required_columns() -> None:
    nullable = {col.name for col in Room.__table__.columns if col.nullable}
    assert "organization_id" not in nullable
    assert "floor_id" not in nullable
    assert "room_number" not in nullable
    assert "room_type" not in nullable


def test_room_has_no_capacity_columns() -> None:
    columns = {col.name for col in Room.__table__.columns}
    assert not {"capacity", "max_capacity", "max_beds", "bed_count"} & columns


def test_room_enum_column_type() -> None:
    column = Room.__table__.c["room_type"]
    assert column.type.name == "room_type"
    assert list(column.type.enums) == [t.value for t in RoomTypeEnum]


def test_room_indexes() -> None:
    indexed = {idx.columns.keys()[0] for idx in Room.__table__.indexes}
    assert "organization_id" in indexed
    assert "floor_id" in indexed
    assert "room_number" in indexed


def test_room_unique_floor_number() -> None:
    uniques = {
        tuple(c.columns.keys())
        for c in Room.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("floor_id", "room_number") in uniques


def test_room_timestamps() -> None:
    assert "created_at" in Room.__table__.columns
    assert "updated_at" in Room.__table__.columns


def test_room_relationships_compile() -> None:
    configure_mappers()
    floor = Floor(building=None, floor_number=1, name="First Floor")
    room = Room(floor=floor, room_number="A101", room_type=RoomTypeEnum.FOUR_SHARE)
    bed = Bed(room=room, bed_number="1")
    assert room.floor is floor
    assert room in floor.rooms
    assert bed.room is room
    assert bed in room.beds