"""Tests for resident profile schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.resident_profile import ResidentProfile
from app.schemas.resident_profile import ResidentProfileCreate, ResidentProfileRead


def profile_kwargs(**overrides: object) -> dict[str, object]:
    return {
        "organization_id": uuid4(),
        "organization_member_id": uuid4(),
        "emergency_contact_name": "Bob",
        "emergency_contact_phone": "9999999999",
        "address": "12 Main St",
        **overrides,
    }


def test_resident_profile_create_valid() -> None:
    data = ResidentProfileCreate(**profile_kwargs())
    assert data.emergency_contact_name == "Bob"
    assert data.emergency_contact_phone == "9999999999"
    assert data.address == "12 Main St"
    assert data.property_id is None
    assert data.notes is None
    assert data.is_active is True


def test_resident_profile_create_strips_and_defaults() -> None:
    data = ResidentProfileCreate(
        **profile_kwargs(
            emergency_contact_name="  Bob  ",
            emergency_contact_phone="  9999999999  ",
            address="  12 Main St  ",
            notes="  Returning resident  ",
            property_id=uuid4(),
            is_active=False,
        )
    )
    assert data.emergency_contact_name == "Bob"
    assert data.emergency_contact_phone == "9999999999"
    assert data.address == "12 Main St"
    assert data.notes == "Returning resident"
    assert data.property_id is not None
    assert data.is_active is False


def test_resident_profile_create_requires_member() -> None:
    with pytest.raises(ValidationError):
        ResidentProfileCreate(
            organization_id=uuid4(),
            emergency_contact_name="Bob",
            emergency_contact_phone="9999999999",
            address="12 Main St",
        )


def test_resident_profile_create_rejects_blank_contact_name() -> None:
    with pytest.raises(ValidationError):
        ResidentProfileCreate(**profile_kwargs(emergency_contact_name=""))


def test_resident_profile_create_rejects_blank_phone() -> None:
    with pytest.raises(ValidationError):
        ResidentProfileCreate(**profile_kwargs(emergency_contact_phone=""))


def test_resident_profile_create_rejects_long_notes() -> None:
    with pytest.raises(ValidationError):
        ResidentProfileCreate(**profile_kwargs(notes="a" * 4001))


def test_resident_profile_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        ResidentProfileCreate(**profile_kwargs(user_id=uuid4()))


def test_resident_profile_read_from_attributes() -> None:
    now = datetime.now(UTC)
    profile = ResidentProfile(
        id=uuid4(),
        organization_id=uuid4(),
        organization_member_id=uuid4(),
        property_id=None,
        emergency_contact_name="Bob",
        emergency_contact_phone="9999999999",
        address="12 Main St",
        notes=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    read = ResidentProfileRead.model_validate(profile)
    assert read.id == profile.id
    assert read.organization_member_id == profile.organization_member_id
    assert read.emergency_contact_name == "Bob"
    assert read.address == "12 Main St"
    assert read.is_active is True
    assert read.created_at == now