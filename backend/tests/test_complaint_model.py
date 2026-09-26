"""Complaint model: enum-backed columns, defaults, and relationship wiring."""

from uuid import uuid4

from app.models.complaint import Complaint
from app.models.enums import (
    ComplaintCategoryEnum,
    ComplaintPriorityEnum,
    ComplaintStatusEnum,
)
from app.repositories.organization import OrganizationRepository
from app.schemas.organization import OrganizationCreate


def test_table_name_is_complaints() -> None:
    assert Complaint.__tablename__ == "complaints"


def test_enums_have_approved_members() -> None:
    assert {c.value for c in ComplaintCategoryEnum} == {
        "MAINTENANCE",
        "ELECTRICAL",
        "PLUMBING",
        "FOOD",
        "HOUSEKEEPING",
        "SECURITY",
        "INTERNET",
        "OTHER",
    }
    assert {p.value for p in ComplaintPriorityEnum} == {
        "LOW",
        "MEDIUM",
        "HIGH",
        "URGENT",
    }
    assert {s.value for s in ComplaintStatusEnum} == {
        "OPEN",
        "IN_PROGRESS",
        "ON_HOLD",
        "RESOLVED",
        "CLOSED",
    }


def test_status_order_is_the_workflow_order() -> None:
    """The service derives legal transitions from declaration order, so the order
    is part of the contract: forward, backward, and CLOSED terminal."""
    assert [s.value for s in ComplaintStatusEnum] == [
        "OPEN",
        "IN_PROGRESS",
        "ON_HOLD",
        "RESOLVED",
        "CLOSED",
    ]


def test_defaults_are_medium_priority_and_open(db_session) -> None:
    org = OrganizationRepository(db_session).create(
        OrganizationCreate(name="ABC PG", slug=f"abc-{uuid4().hex[:8]}"),
    )
    complaint = Complaint(
        organization_id=org.id,
        property_id=uuid4(),
        resident_profile_id=uuid4(),
        title="Tap leaking",
        description="The bathroom tap drips constantly.",
        category=ComplaintCategoryEnum.PLUMBING,
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)

    assert complaint.priority == ComplaintPriorityEnum.MEDIUM
    assert complaint.status == ComplaintStatusEnum.OPEN
    assert complaint.assigned_to_member_id is None
    assert complaint.resolved_at is None


def test_organization_back_populates_complaints(db_session) -> None:
    org = OrganizationRepository(db_session).create(
        OrganizationCreate(name="ABC PG", slug=f"abc-{uuid4().hex[:8]}"),
    )
    complaint = Complaint(
        organization_id=org.id,
        property_id=uuid4(),
        resident_profile_id=uuid4(),
        title="No hot water",
        description="Shower has been cold for two days.",
        category=ComplaintCategoryEnum.MAINTENANCE,
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(org)

    assert org.complaints == [complaint]
    assert complaint.organization is org
