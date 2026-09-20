"""Tests for floor schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.floor import Floor
from app.schemas.floor import FloorCreate, FloorRead


def test_floor_create_valid() -> None:
    data = FloorCreate(
        organization_id=uuid4(),
        building_id=uuid4(),
        floor_number=0,
        name="  Ground Floor  ",
    )
    assert data.floor_number == 0
    assert data.name == "Ground Floor"


def test_floor_create_requires_org_and_building() -> None:
    with pytest.raises(ValidationError):
        FloorCreate(floor_number=1, name="First Floor")


def test_floor_create_rejects_negative_number() -> None:
    with pytest.raises(ValidationError):
        FloorCreate(
            organization_id=uuid4(),
            building_id=uuid4(),
            floor_number=-1,
            name="Basement",
        )


def test_floor_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        FloorCreate(organization_id=uuid4(), building_id=uuid4(), floor_number=1, name="")


def test_floor_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        FloorCreate(
            organization_id=uuid4(),
            building_id=uuid4(),
            floor_number=1,
            name="First Floor",
            rooms=[],
        )


def test_floor_read_from_attributes() -> None:
    now = datetime.now(UTC)
    floor = Floor(
        id=uuid4(),
        organization_id=uuid4(),
        building_id=uuid4(),
        floor_number=2,
        name="Second Floor",
        created_at=now,
        updated_at=now,
    )
    read = FloorRead.model_validate(floor)
    assert read.id == floor.id
    assert read.building_id == floor.building_id
    assert read.floor_number == 2
    assert read.name == "Second Floor"
    assert read.created_at == now