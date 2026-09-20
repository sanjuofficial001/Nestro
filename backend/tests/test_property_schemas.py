"""Tests for property schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import PropertyStatusEnum, PropertyTypeEnum
from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertyRead


def test_property_create_valid() -> None:
    data = PropertyCreate(
        name="  PSG Boys PG  ",
        property_type=PropertyTypeEnum.PG,
        organization_id=uuid4(),
    )
    assert data.name == "PSG Boys PG"
    assert data.property_type is PropertyTypeEnum.PG
    assert data.status is PropertyStatusEnum.ACTIVE
    assert data.address is None


def test_property_create_with_optional_fields() -> None:
    data = PropertyCreate(
        name="Elite Hostel",
        property_type=PropertyTypeEnum.HOSTEL,
        organization_id=uuid4(),
        address="  Gandhi St, Chennai  ",
        contact_phone="+919000000000",
        rules="No visitors after 10pm",
        status=PropertyStatusEnum.INACTIVE,
    )
    assert data.address == "Gandhi St, Chennai"
    assert data.contact_phone == "+919000000000"
    assert data.rules == "No visitors after 10pm"


def test_property_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate(name="", property_type=PropertyTypeEnum.PG, organization_id=uuid4())


def test_property_create_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate(
            name="x", property_type="VILLA", organization_id=uuid4()
        )


def test_property_create_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate(
            name="x",
            property_type=PropertyTypeEnum.PG,
            status="SOLD",
            organization_id=uuid4(),
        )


def test_property_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate(
            name="x",
            property_type=PropertyTypeEnum.PG,
            organization_id=uuid4(),
            slug="extra",
        )


def test_property_read_from_attributes() -> None:
    now = datetime.now(UTC)
    org_id = uuid4()
    property = Property(
        id=uuid4(),
        organization_id=org_id,
        name="Sunrise Apartments",
        property_type=PropertyTypeEnum.APARTMENT,
        status=PropertyStatusEnum.ACTIVE,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    read = PropertyRead.model_validate(property)
    assert read.id == property.id
    assert read.organization_id == org_id
    assert read.name == "Sunrise Apartments"
    assert read.property_type is PropertyTypeEnum.APARTMENT
    assert read.created_at == now
    assert read.deleted_at is None