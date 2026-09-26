"""Complaint repository: org scoping and SQL-side filters."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.enums import (
    ComplaintCategoryEnum,
    ComplaintPriorityEnum,
    ComplaintStatusEnum,
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
)
from app.repositories.complaint import ComplaintRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.user import UserRepository
from app.schemas.complaint import ComplaintCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.user import UserCreate


def make_org(db_session, *, slug: str):
    return OrganizationRepository(db_session).create(
        OrganizationCreate(name=slug.title(), slug=slug),
    )


def make_profile(db_session, org, prop):
    user = UserRepository(db_session).create(
        UserCreate(
            email=f"tenant-{uuid4().hex[:8]}@example.com",
            phone=None,
            full_name="Test Tenant",
            role=RoleEnum.TENANT,
        ),
    )
    member = OrganizationMemberRepository(db_session).create(
        OrganizationMemberCreate(
            organization_id=org.id, user_id=user.id, role=OrganizationRoleEnum.STAFF
        ),
    )
    return ResidentProfileRepository(db_session).create(
        ResidentProfileCreate(
            organization_id=org.id,
            organization_member_id=member.id,
            property_id=prop.id,
            emergency_contact_name="Asha Rao",
            emergency_contact_phone="9876543210",
            address="12 MG Road",
        ),
    )


def make_complaint(db_session, org, prop, profile, **overrides):
    body = {
        "organization_id": org.id,
        "property_id": prop.id,
        "resident_profile_id": profile.id,
        "title": "Tap leaking",
        "description": "The bathroom tap drips constantly.",
        "category": ComplaintCategoryEnum.PLUMBING,
    }
    body.update(overrides)
    return ComplaintRepository(db_session).create(ComplaintCreate(**body))


def seed(db_session):
    org = make_org(db_session, slug="abc-pg")
    other = make_org(db_session, slug="zzz-pg")
    prop = PropertyRepository(db_session).create(
        PropertyCreate(
            name="PSG Boys PG",
            property_type=PropertyTypeEnum.PG,
            organization_id=org.id,
        ),
    )
    profile = make_profile(db_session, org, prop)
    return org, other, prop, profile


def test_get_by_id_returns_none_for_unknown(db_session) -> None:
    assert ComplaintRepository(db_session).get_by_id(uuid4()) is None


def test_get_by_id_returns_the_complaint(db_session) -> None:
    org, _, prop, profile = seed(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    assert ComplaintRepository(db_session).get_by_id(complaint.id) == complaint


def test_list_is_scoped_to_the_organization(db_session) -> None:
    org, other, prop, profile = seed(db_session)
    mine = make_complaint(db_session, org, prop, profile)

    other_prop = PropertyRepository(db_session).create(
        PropertyCreate(
            name="Annex PG",
            property_type=PropertyTypeEnum.PG,
            organization_id=other.id,
        ),
    )
    other_profile = make_profile(db_session, other, other_prop)
    make_complaint(db_session, other, other_prop, other_profile)

    assert ComplaintRepository(db_session).list_for_org(org.id) == [mine]
    assert len(ComplaintRepository(db_session).list_for_org(other.id)) == 1


def test_list_filters_by_status(db_session) -> None:
    org, _, prop, profile = seed(db_session)
    open_one = make_complaint(db_session, org, prop, profile)
    in_progress = make_complaint(
        db_session,
        org,
        prop,
        profile,
        status=ComplaintStatusEnum.IN_PROGRESS,
        title="Fan broken",
    )

    found = ComplaintRepository(db_session).list_for_org(
        org.id, status=ComplaintStatusEnum.IN_PROGRESS
    )
    assert found == [in_progress]
    assert open_one not in found


def test_list_filters_by_priority(db_session) -> None:
    org, _, prop, profile = seed(db_session)
    make_complaint(db_session, org, prop, profile)
    urgent = make_complaint(
        db_session,
        org,
        prop,
        profile,
        priority=ComplaintPriorityEnum.URGENT,
        title="Gas leak smell",
    )

    found = ComplaintRepository(db_session).list_for_org(
        org.id, priority=ComplaintPriorityEnum.URGENT
    )
    assert found == [urgent]


def test_list_filters_by_resident_profile(db_session) -> None:
    org, _, prop, profile = seed(db_session)
    mine = make_complaint(db_session, org, prop, profile)
    other_resident = make_profile(db_session, org, prop)
    make_complaint(db_session, org, prop, other_resident, title="WiFi weak")

    found = ComplaintRepository(db_session).list_for_org(
        org.id, resident_profile_id=profile.id
    )
    assert found == [mine]


def test_list_combines_filters(db_session) -> None:
    org, _, prop, profile = seed(db_session)
    target = make_complaint(
        db_session,
        org,
        prop,
        profile,
        status=ComplaintStatusEnum.ON_HOLD,
        priority=ComplaintPriorityEnum.HIGH,
    )
    make_complaint(db_session, org, prop, profile, status=ComplaintStatusEnum.OPEN)
    make_complaint(
        db_session, org, prop, profile, status=ComplaintStatusEnum.ON_HOLD
    )

    found = ComplaintRepository(db_session).list_for_org(
        org.id,
        status=ComplaintStatusEnum.ON_HOLD,
        priority=ComplaintPriorityEnum.HIGH,
    )
    assert found == [target]


def test_list_returns_empty_for_org_with_no_complaints(db_session) -> None:
    org, _, _, _ = seed(db_session)
    assert ComplaintRepository(db_session).list_for_org(org.id) == []


def test_list_orders_newest_first(db_session) -> None:
    """Ordering is by `created_at` desc. The column is a server default, so the test
    stamps it explicitly — SQLite's CURRENT_TIMESTAMP has second resolution and
    cannot separate two rows created back to back."""
    org, _, prop, profile = seed(db_session)
    first = make_complaint(db_session, org, prop, profile, title="First")
    second = make_complaint(db_session, org, prop, profile, title="Second")
    first.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    second.created_at = datetime(2026, 6, 1, tzinfo=UTC)
    db_session.commit()

    found = ComplaintRepository(db_session).list_for_org(org.id)
    assert [c.id for c in found] == [second.id, first.id]
