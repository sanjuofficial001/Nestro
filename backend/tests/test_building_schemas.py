"""Tests for building schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.building import Building
from app.schemas.building import BuildingCreate, BuildingRead


def test_building_create_valid() -> None:
    data = BuildingCreate(
        name="  Block A  ",
        organization_id=uuid4(),
        property_id=uuid4(),
    )
    assert data.name == "Block A"
    assert data.description is None


def test_building_create_strips_description() -> None:
    data = BuildingCreate(
        name="Block B",
        description="  North wing  ",
        organization_id=uuid4(),
        property_id=uuid4(),
    )
    assert data.description == "North wing"


def test_building_create_requires_org_and_property() -> None:
    with pytest.raises(ValidationError):
        BuildingCreate(name="Block A")


def test_building_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        BuildingCreate(name="", organization_id=uuid4(), property_id=uuid4())


def test_building_create_rejects_long_description() -> None:
    with pytest.raises(ValidationError):
        BuildingCreate(
            name="x",
            description="a" * 1001,
            organization_id=uuid4(),
            property_id=uuid4(),
        )


def test_building_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        BuildingCreate(
            name="x",
            organization_id=uuid4(),
            property_id=uuid4(),
            floors=[],
        )


def test_building_read_from_attributes() -> None:
    now = datetime.now(UTC)
    building = Building(
        id=uuid4(),
        organization_id=uuid4(),
        property_id=uuid4(),
        name="Block A",
        description=None,
        created_at=now,
        updated_at=now,
    )
    read = BuildingRead.model_validate(building)
    assert read.id == building.id
    assert read.organization_id == building.organization_id
    assert read.property_id == building.property_id
    assert read.name == "Block A"
    assert read.created_at == now