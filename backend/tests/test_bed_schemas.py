"""Tests for bed schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.bed import Bed
from app.models.enums import BedStatusEnum
from app.schemas.bed import BedCreate, BedRead


def test_bed_create_valid() -> None:
    data = BedCreate(
        organization_id=uuid4(),
        room_id=uuid4(),
        bed_number="  1  ",
        status=BedStatusEnum.AVAILABLE,
    )
    assert data.bed_number == "1"
    assert data.status is BedStatusEnum.AVAILABLE


def test_bed_create_default_status() -> None:
    data = BedCreate(organization_id=uuid4(), room_id=uuid4(), bed_number="B2")
    assert data.status is BedStatusEnum.AVAILABLE


def test_bed_create_requires_org_and_room() -> None:
    with pytest.raises(ValidationError):
        BedCreate(bed_number="1")


def test_bed_create_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        BedCreate(
            organization_id=uuid4(),
            room_id=uuid4(),
            bed_number="1",
            status="RESERVED",
        )


def test_bed_create_rejects_blank_number() -> None:
    with pytest.raises(ValidationError):
        BedCreate(organization_id=uuid4(), room_id=uuid4(), bed_number="")


def test_bed_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        BedCreate(
            organization_id=uuid4(),
            room_id=uuid4(),
            bed_number="1",
            tenant_id=uuid4(),
        )


def test_bed_read_from_attributes() -> None:
    now = datetime.now(UTC)
    bed = Bed(
        id=uuid4(),
        organization_id=uuid4(),
        room_id=uuid4(),
        bed_number="3",
        status=BedStatusEnum.MAINTENANCE,
        created_at=now,
        updated_at=now,
    )
    read = BedRead.model_validate(bed)
    assert read.id == bed.id
    assert read.room_id == bed.room_id
    assert read.bed_number == "3"
    assert read.status is BedStatusEnum.MAINTENANCE
    assert read.created_at == now