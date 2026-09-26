"""Complaint schema validation: length bounds, stripping, and what may be edited."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import (
    ComplaintCategoryEnum,
    ComplaintPriorityEnum,
    ComplaintStatusEnum,
)
from app.schemas.complaint import ComplaintCreate
from app.schemas.complaint_api import ComplaintUpdate


def payload(**overrides) -> dict:
    body = {
        "organization_id": str(uuid4()),
        "property_id": str(uuid4()),
        "resident_profile_id": str(uuid4()),
        "title": "Tap leaking",
        "description": "The bathroom tap drips constantly.",
        "category": "PLUMBING",
    }
    body.update(overrides)
    return body


def test_create_defaults_priority_and_status() -> None:
    created = ComplaintCreate(**payload())
    assert created.priority == ComplaintPriorityEnum.MEDIUM
    assert created.status == ComplaintStatusEnum.OPEN
    assert created.assigned_to_member_id is None


def test_create_accepts_every_category() -> None:
    for category in ComplaintCategoryEnum:
        assert ComplaintCreate(**payload(category=category.value)).category == category


def test_create_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(**payload(category="NOT_A_CATEGORY"))


def test_create_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(**payload(resolved_at="2026-01-01T00:00:00Z"))


def test_title_strips_surrounding_whitespace() -> None:
    assert ComplaintCreate(**payload(title="  Tap leaking  ")).title == "Tap leaking"


def test_description_strips_surrounding_whitespace() -> None:
    created = ComplaintCreate(**payload(description="  drips constantly  "))
    assert created.description == "drips constantly"


def test_title_rejects_over_200_chars() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(**payload(title="x" * 201))


def test_title_accepts_exactly_200_chars() -> None:
    assert len(ComplaintCreate(**payload(title="x" * 200)).title) == 200


def test_description_rejects_over_2000_chars() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(**payload(description="x" * 2001))


def test_description_accepts_exactly_2000_chars() -> None:
    assert len(ComplaintCreate(**payload(description="x" * 2000)).description) == 2000


def test_blank_title_after_strip_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(**payload(title="   "))


def test_update_allows_only_the_editable_subset() -> None:
    update = ComplaintUpdate(
        title="  Fixed  ",
        description="  plumber visited  ",
        status=ComplaintStatusEnum.IN_PROGRESS,
        priority=ComplaintPriorityEnum.HIGH,
        assigned_to_member_id=uuid4(),
    )
    assert update.title == "Fixed"
    assert update.description == "plumber visited"
    assert update.status == ComplaintStatusEnum.IN_PROGRESS
    assert update.priority == ComplaintPriorityEnum.HIGH


def test_update_rejects_category_as_immovable() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(category=ComplaintCategoryEnum.FOOD)


def test_update_rejects_organization_id_as_immovable() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(organization_id=uuid4())


def test_update_rejects_property_id_as_immovable() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(property_id=uuid4())


def test_update_rejects_resident_profile_id_as_immovable() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(resident_profile_id=uuid4())


def test_update_rejects_resolved_at() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(resolved_at="2026-01-01T00:00:00Z")


def test_update_rejects_over_200_char_title() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(title="x" * 201)


def test_update_rejects_over_2000_char_description() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(description="x" * 2001)


def test_update_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        ComplaintUpdate(status="ESCALATED")
