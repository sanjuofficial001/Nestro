"""Tests for room schema validation.

Room schemas must never expose capacity — a room's size is derived from its
bed count, so no capacity field is allowed on any payload.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import RoomTypeEnum
from app.models.room import Room
from app.schemas.room import RoomBase, RoomCreate, RoomRead


def test_room_create_valid() -> None:
    data = RoomCreate(
        organization_id=uuid4(),
        floor_id=uuid4(),
        room_number="  A101  ",
        room_type=RoomTypeEnum.FOUR_SHARE,
    )
    assert data.room_number == "A101"
    assert data.room_type is RoomTypeEnum.FOUR_SHARE


def test_room_create_requires_org_and_floor() -> None:
    with pytest.raises(ValidationError):
        RoomCreate(room_number="A101", room_type=RoomTypeEnum.SINGLE)


def test_room_create_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        RoomCreate(
            organization_id=uuid4(),
            floor_id=uuid4(),
            room_number="A101",
            room_type="PENTHOUSE",
        )


def test_room_create_rejects_blank_number() -> None:
    with pytest.raises(ValidationError):
        RoomCreate(
            organization_id=uuid4(),
            floor_id=uuid4(),
            room_number="",
            room_type=RoomTypeEnum.SINGLE,
        )


def test_room_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        RoomCreate(
            organization_id=uuid4(),
            floor_id=uuid4(),
            room_number="A101",
            room_type=RoomTypeEnum.SINGLE,
            beds=[],
        )


def test_room_schemas_have_no_capacity_field() -> None:
    forbidden = {"capacity", "max_capacity", "max_beds", "bed_count"}
    assert forbidden.isdisjoint(RoomBase.model_fields)
    assert forbidden.isdisjoint(RoomCreate.model_fields)
    assert forbidden.isdisjoint(RoomRead.model_fields)


def test_room_read_rejects_capacity_field() -> None:
    now = datetime.now(UTC)
    room = Room(
        id=uuid4(),
        organization_id=uuid4(),
        floor_id=uuid4(),
        room_number="A101",
        room_type=RoomTypeEnum.SINGLE,
        created_at=now,
        updated_at=now,
    )
    read = RoomRead.model_validate(room)
    assert read.id == room.id
    assert read.floor_id == room.floor_id
    assert read.room_number == "A101"
    assert read.room_type is RoomTypeEnum.SINGLE
    assert read.created_at == now
    assert not hasattr(read, "capacity")