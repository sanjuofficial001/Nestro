"""Tests for tenant stay schema validation."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import TenantStayStatusEnum
from app.models.tenant_stay import TenantStay
from app.schemas.tenant_stay import TenantStayCreate, TenantStayRead


def stay_kwargs(**overrides: object) -> dict[str, object]:
    return {
        "organization_id": uuid4(),
        "resident_profile_id": uuid4(),
        "property_id": uuid4(),
        "bed_id": uuid4(),
        "start_date": date(2026, 1, 1),
        **overrides,
    }


def test_tenant_stay_create_valid_defaults() -> None:
    data = TenantStayCreate(**stay_kwargs())
    assert data.start_date == date(2026, 1, 1)
    assert data.end_date is None
    assert data.status == TenantStayStatusEnum.ACTIVE
    assert data.notes is None


def test_tenant_stay_create_strips_and_accepts_end() -> None:
    data = TenantStayCreate(
        **stay_kwargs(
            end_date=date(2026, 2, 1),
            status=TenantStayStatusEnum.COMPLETED,
            notes="  Left with room key  ",
        )
    )
    assert data.end_date == date(2026, 2, 1)
    assert data.status == TenantStayStatusEnum.COMPLETED
    assert data.notes == "Left with room key"


def test_tenant_stay_create_requires_start_date() -> None:
    with pytest.raises(ValidationError):
        TenantStayCreate(resident_profile_id=uuid4(), bed_id=uuid4())


def test_tenant_stay_create_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        TenantStayCreate(**stay_kwargs(status="OPEN"))


def test_tenant_stay_create_rejects_long_notes() -> None:
    with pytest.raises(ValidationError):
        TenantStayCreate(**stay_kwargs(notes="a" * 4001))


def test_tenant_stay_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        TenantStayCreate(**stay_kwargs(tenant_id=uuid4()))


def test_tenant_stay_read_from_attributes() -> None:
    now = datetime.now(UTC)
    stay = TenantStay(
        id=uuid4(),
        organization_id=uuid4(),
        resident_profile_id=uuid4(),
        property_id=uuid4(),
        bed_id=uuid4(),
        start_date=date(2026, 1, 1),
        end_date=None,
        status=TenantStayStatusEnum.ACTIVE,
        notes=None,
        created_at=now,
        updated_at=now,
    )
    read = TenantStayRead.model_validate(stay)
    assert read.id == stay.id
    assert read.start_date == date(2026, 1, 1)
    assert read.end_date is None
    assert read.status == TenantStayStatusEnum.ACTIVE
    assert read.created_at == now


def test_tenant_stay_read_accepts_end_date() -> None:
    now = datetime.now(UTC)
    stay = TenantStay(
        id=uuid4(),
        organization_id=uuid4(),
        resident_profile_id=uuid4(),
        property_id=uuid4(),
        bed_id=uuid4(),
        start_date=date(2025, 6, 1),
        end_date=date(2025, 9, 1),
        status=TenantStayStatusEnum.COMPLETED,
        notes="Paid",
        created_at=now,
        updated_at=now,
    )
    read = TenantStayRead.model_validate(stay)
    assert read.end_date == date(2025, 9, 1)
    assert read.notes == "Paid"