"""Service-layer complaint CRUD: org membership, role enforcement, reference
validation, and the one-step status lifecycle."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.complaint import Complaint
from app.models.enums import (
    ComplaintCategoryEnum,
    ComplaintPriorityEnum,
    ComplaintStatusEnum,
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
)
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.property import Property
from app.models.resident_profile import ResidentProfile
from app.models.user import User
from app.repositories.complaint import ComplaintRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.user import UserRepository
from app.schemas.complaint import ComplaintCreate
from app.schemas.complaint_api import ComplaintUpdate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.user import UserCreate
from app.services.complaint_service import ComplaintService


def make_user(db_session, *, role: RoleEnum) -> User:
    user = UserRepository(db_session).create(
        UserCreate(
            email=f"{role.value.lower()}-{uuid4().hex[:8]}@example.com",
            phone=None,
            full_name="Test User",
            role=role,
        ),
    )
    db_session.commit()
    db_session.refresh(user)
    return user


def make_org(db_session, *, slug: str) -> Organization:
    return OrganizationRepository(db_session).create(
        OrganizationCreate(name=slug.title(), slug=slug),
    )


def make_member(
    db_session, org, user, *, role: OrganizationRoleEnum = OrganizationRoleEnum.STAFF
) -> OrganizationMember:
    return OrganizationMemberRepository(db_session).create(
        OrganizationMemberCreate(organization_id=org.id, user_id=user.id, role=role),
    )


def make_property(db_session, org, *, name: str = "PSG Boys PG") -> Property:
    return PropertyRepository(db_session).create(
        PropertyCreate(
            name=name,
            property_type=PropertyTypeEnum.PG,
            organization_id=org.id,
        ),
    )


def make_profile(db_session, org, prop) -> ResidentProfile:
    resident = make_user(db_session, role=RoleEnum.TENANT)
    member = make_member(db_session, org, resident)
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


def service(db_session) -> ComplaintService:
    return ComplaintService(db_session)


def seed_org(db_session, *, slug: str = "abc-pg"):
    """An org with a property, a resident, and an OWNER caller."""
    org = make_org(db_session, slug=slug)
    prop = make_property(db_session, org)
    profile = make_profile(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    return org, owner, prop, profile


def payload(org, prop, profile, **overrides) -> ComplaintCreate:
    body = {
        "organization_id": org.id,
        "property_id": prop.id,
        "resident_profile_id": profile.id,
        "title": "Tap leaking",
        "description": "The bathroom tap drips constantly.",
        "category": ComplaintCategoryEnum.PLUMBING,
    }
    body.update(overrides)
    return ComplaintCreate(**body)


def make_complaint(db_session, org, prop, profile, **overrides) -> Complaint:
    return ComplaintRepository(db_session).create(payload(org, prop, profile, **overrides))


def seed_caller(db_session, org, *, role: RoleEnum, member_role: OrganizationRoleEnum):
    user = make_user(db_session, role=role)
    make_member(db_session, org, user, role=member_role)
    return user


# --- create -----------------------------------------------------------------


def test_create_complaint_owner_succeeds(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)

    complaint = service(db_session).create_complaint(
        owner, payload(org, prop, profile)
    )
    assert complaint.id is not None
    assert complaint.organization_id == org.id
    assert complaint.property_id == prop.id
    assert complaint.resident_profile_id == profile.id
    assert complaint.category == ComplaintCategoryEnum.PLUMBING
    assert complaint.priority == ComplaintPriorityEnum.MEDIUM
    assert complaint.status == ComplaintStatusEnum.OPEN
    assert complaint.assigned_to_member_id is None
    assert complaint.resolved_at is None


def test_create_complaint_manager_succeeds(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    manager = seed_caller(
        db_session, org, role=RoleEnum.MANAGER, member_role=OrganizationRoleEnum.MANAGER
    )

    complaint = service(db_session).create_complaint(
        manager, payload(org, prop, profile)
    )
    assert complaint.status == ComplaintStatusEnum.OPEN


def test_create_complaint_super_admin_bypasses(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    complaint = service(db_session).create_complaint(
        admin, payload(org, prop, profile)
    )
    assert complaint.organization_id == org.id


def test_create_complaint_staff_denied(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    staff = seed_caller(
        db_session, org, role=RoleEnum.STAFF, member_role=OrganizationRoleEnum.STAFF
    )

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_complaint(staff, payload(org, prop, profile))


def test_create_complaint_non_member_denied(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_complaint(outsider, payload(org, prop, profile))


def test_create_complaint_unknown_property_not_found(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)

    with pytest.raises(NotFoundError, match="property not found"):
        service(db_session).create_complaint(
            owner, payload(org, prop, profile, property_id=uuid4())
        )


def test_create_complaint_foreign_property_conflict(db_session) -> None:
    org, owner, _, profile = seed_org(db_session)
    other_org = make_org(db_session, slug="zzz-pg")
    foreign_prop = make_property(db_session, other_org, name="Annex PG")

    with pytest.raises(ValueError, match="property does not belong"):
        service(db_session).create_complaint(
            owner, payload(org, foreign_prop, profile)
        )


def test_create_complaint_unknown_resident_not_found(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)

    with pytest.raises(NotFoundError, match="resident profile not found"):
        service(db_session).create_complaint(
            owner, payload(org, prop, profile, resident_profile_id=uuid4())
        )


def test_create_complaint_foreign_resident_conflict(db_session) -> None:
    org, owner, prop, _ = seed_org(db_session)
    other_org = make_org(db_session, slug="zzz-pg")
    other_prop = make_property(db_session, other_org, name="Annex PG")
    foreign_profile = make_profile(db_session, other_org, other_prop)

    with pytest.raises(ValueError, match="resident profile does not belong"):
        service(db_session).create_complaint(
            owner, payload(org, prop, foreign_profile)
        )


def test_create_complaint_with_assignee_succeeds(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    assignee = seed_caller(
        db_session, org, role=RoleEnum.STAFF, member_role=OrganizationRoleEnum.STAFF
    )
    member_id = OrganizationMemberRepository(db_session).get_for_user(assignee.id)[0].id

    complaint = service(db_session).create_complaint(
        owner, payload(org, prop, profile, assigned_to_member_id=member_id)
    )
    assert complaint.assigned_to_member_id == member_id


def test_create_complaint_unknown_assignee_not_found(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)

    with pytest.raises(NotFoundError, match="organization member not found"):
        service(db_session).create_complaint(
            owner, payload(org, prop, profile, assigned_to_member_id=uuid4())
        )


def test_create_complaint_foreign_assignee_conflict(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    other_org = make_org(db_session, slug="zzz-pg")
    outsider = make_user(db_session, role=RoleEnum.STAFF)
    foreign_member = make_member(db_session, other_org, outsider)

    with pytest.raises(ValueError, match="organization member does not belong"):
        service(db_session).create_complaint(
            owner,
            payload(org, prop, profile, assigned_to_member_id=foreign_member.id),
        )


# --- list -------------------------------------------------------------------


def test_list_complaints_owner_sees_own_org(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    mine = make_complaint(db_session, org, prop, profile)
    other_org = make_org(db_session, slug="zzz-pg")
    other_prop = make_property(db_session, other_org, name="Annex PG")
    other_profile = make_profile(db_session, other_org, other_prop)
    make_complaint(db_session, other_org, other_prop, other_profile)

    assert service(db_session).list_complaints(owner, org.id) == [mine]


def test_list_complaints_staff_may_read(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    staff = seed_caller(
        db_session, org, role=RoleEnum.STAFF, member_role=OrganizationRoleEnum.STAFF
    )

    assert service(db_session).list_complaints(staff, org.id) == [complaint]


def test_list_complaints_non_member_denied(db_session) -> None:
    org, _, _, _ = seed_org(db_session)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_complaints(outsider, org.id)


def test_list_complaints_filters_by_status_and_priority(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    target = make_complaint(
        db_session,
        org,
        prop,
        profile,
        status=ComplaintStatusEnum.IN_PROGRESS,
        priority=ComplaintPriorityEnum.HIGH,
    )
    make_complaint(db_session, org, prop, profile)

    assert service(db_session).list_complaints(
        owner, org.id, status=ComplaintStatusEnum.IN_PROGRESS
    ) == [target]
    assert service(db_session).list_complaints(
        owner, org.id, priority=ComplaintPriorityEnum.HIGH
    ) == [target]
    assert service(db_session).list_complaints(
        owner, org.id, status=ComplaintStatusEnum.CLOSED
    ) == []


def test_list_complaints_filters_by_resident(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    mine = make_complaint(db_session, org, prop, profile)
    other_resident = make_profile(db_session, org, prop)
    make_complaint(db_session, org, prop, other_resident, title="WiFi weak")

    assert service(db_session).list_complaints(
        owner, org.id, resident_profile_id=profile.id
    ) == [mine]


def test_list_complaints_foreign_resident_filter_is_not_found(db_session) -> None:
    """A filter id from another org must be indistinguishable from a missing one, so
    listing never reveals that the resident exists elsewhere."""
    org, owner, _, _ = seed_org(db_session)
    other_org = make_org(db_session, slug="zzz-pg")
    other_prop = make_property(db_session, other_org, name="Annex PG")
    foreign_profile = make_profile(db_session, other_org, other_prop)

    with pytest.raises(NotFoundError, match="resident profile not found"):
        service(db_session).list_complaints(
            owner, org.id, resident_profile_id=foreign_profile.id
        )


def test_list_complaints_unknown_resident_filter_is_not_found(db_session) -> None:
    org, owner, _, _ = seed_org(db_session)

    with pytest.raises(NotFoundError, match="resident profile not found"):
        service(db_session).list_complaints(
            owner, org.id, resident_profile_id=uuid4()
        )


# --- get --------------------------------------------------------------------


def test_get_complaint_owner_succeeds(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    assert service(db_session).get_complaint(owner, complaint.id) == complaint


def test_get_complaint_staff_may_read(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    staff = seed_caller(
        db_session, org, role=RoleEnum.STAFF, member_role=OrganizationRoleEnum.STAFF
    )
    assert service(db_session).get_complaint(staff, complaint.id) == complaint


def test_get_complaint_unknown_not_found(db_session) -> None:
    org, owner, _, _ = seed_org(db_session)
    with pytest.raises(NotFoundError, match="complaint not found"):
        service(db_session).get_complaint(owner, uuid4())


def test_get_complaint_non_member_denied(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).get_complaint(outsider, complaint.id)


# --- update: fields ---------------------------------------------------------


def test_update_complaint_title_and_description(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    updated = service(db_session).update_complaint(
        owner, complaint.id, ComplaintUpdate(title="Fan broken", description="Fan stopped")
    )
    assert updated.title == "Fan broken"
    assert updated.description == "Fan stopped"


def test_update_complaint_priority(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    updated = service(db_session).update_complaint(
        owner, complaint.id, ComplaintUpdate(priority=ComplaintPriorityEnum.URGENT)
    )
    assert updated.priority == ComplaintPriorityEnum.URGENT


def test_update_complaint_assignee(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    assignee = seed_caller(
        db_session, org, role=RoleEnum.STAFF, member_role=OrganizationRoleEnum.STAFF
    )
    member_id = OrganizationMemberRepository(db_session).get_for_user(assignee.id)[0].id

    updated = service(db_session).update_complaint(
        owner, complaint.id, ComplaintUpdate(assigned_to_member_id=member_id)
    )
    assert updated.assigned_to_member_id == member_id


def test_update_complaint_foreign_assignee_conflict(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    other_org = make_org(db_session, slug="zzz-pg")
    outsider = make_user(db_session, role=RoleEnum.STAFF)
    foreign_member = make_member(db_session, other_org, outsider)

    with pytest.raises(ValueError, match="organization member does not belong"):
        service(db_session).update_complaint(
            owner,
            complaint.id,
            ComplaintUpdate(assigned_to_member_id=foreign_member.id),
        )


def test_update_complaint_unknown_assignee_not_found(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    with pytest.raises(NotFoundError, match="organization member not found"):
        service(db_session).update_complaint(
            owner, complaint.id, ComplaintUpdate(assigned_to_member_id=uuid4())
        )


def test_update_complaint_staff_denied(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    staff = seed_caller(
        db_session, org, role=RoleEnum.STAFF, member_role=OrganizationRoleEnum.STAFF
    )

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).update_complaint(
            staff, complaint.id, ComplaintUpdate(title="Nope")
        )


def test_update_complaint_unknown_not_found(db_session) -> None:
    org, owner, _, _ = seed_org(db_session)
    with pytest.raises(NotFoundError, match="complaint not found"):
        service(db_session).update_complaint(
            owner, uuid4(), ComplaintUpdate(title="Nope")
        )


def test_update_never_writes_resolved_at(db_session) -> None:
    """`resolved_at` belongs to the workflow milestone, so even a RESOLVED transition
    leaves it null."""
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    for target in (
        ComplaintStatusEnum.IN_PROGRESS,
        ComplaintStatusEnum.ON_HOLD,
        ComplaintStatusEnum.RESOLVED,
    ):
        complaint = service(db_session).update_complaint(
            owner, complaint.id, ComplaintUpdate(status=target)
        )

    assert complaint.status == ComplaintStatusEnum.RESOLVED
    assert complaint.resolved_at is None


# --- update: status lifecycle ----------------------------------------------


@pytest.mark.parametrize("step", [1, 2, 3])
def test_status_may_step_forward(db_session, step: int) -> None:
    order = [
        ComplaintStatusEnum.IN_PROGRESS,
        ComplaintStatusEnum.ON_HOLD,
        ComplaintStatusEnum.RESOLVED,
    ]
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    for target in order[:step]:
        complaint = service(db_session).update_complaint(
            owner, complaint.id, ComplaintUpdate(status=target)
        )
    assert complaint.status == order[step - 1]


def test_status_may_step_backward(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(
        db_session, org, prop, profile, status=ComplaintStatusEnum.RESOLVED
    )

    updated = service(db_session).update_complaint(
        owner, complaint.id, ComplaintUpdate(status=ComplaintStatusEnum.ON_HOLD)
    )
    assert updated.status == ComplaintStatusEnum.ON_HOLD


def test_status_no_op_is_allowed(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(
        db_session, org, prop, profile, status=ComplaintStatusEnum.ON_HOLD
    )

    updated = service(db_session).update_complaint(
        owner, complaint.id, ComplaintUpdate(status=ComplaintStatusEnum.ON_HOLD)
    )
    assert updated.status == ComplaintStatusEnum.ON_HOLD


def test_status_closed_is_reachable_from_resolved(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(
        db_session, org, prop, profile, status=ComplaintStatusEnum.RESOLVED
    )

    updated = service(db_session).update_complaint(
        owner, complaint.id, ComplaintUpdate(status=ComplaintStatusEnum.CLOSED)
    )
    assert updated.status == ComplaintStatusEnum.CLOSED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ComplaintStatusEnum.OPEN, ComplaintStatusEnum.ON_HOLD),
        (ComplaintStatusEnum.OPEN, ComplaintStatusEnum.RESOLVED),
        (ComplaintStatusEnum.OPEN, ComplaintStatusEnum.CLOSED),
        (ComplaintStatusEnum.IN_PROGRESS, ComplaintStatusEnum.RESOLVED),
        (ComplaintStatusEnum.IN_PROGRESS, ComplaintStatusEnum.CLOSED),
        (ComplaintStatusEnum.ON_HOLD, ComplaintStatusEnum.CLOSED),
    ],
)
def test_status_jump_forward_rejected(
    db_session, current: ComplaintStatusEnum, target: ComplaintStatusEnum
) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile, status=current)

    with pytest.raises(ValueError, match="invalid complaint status transition"):
        service(db_session).update_complaint(
            owner, complaint.id, ComplaintUpdate(status=target)
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ComplaintStatusEnum.ON_HOLD, ComplaintStatusEnum.OPEN),
        (ComplaintStatusEnum.RESOLVED, ComplaintStatusEnum.IN_PROGRESS),
        (ComplaintStatusEnum.RESOLVED, ComplaintStatusEnum.OPEN),
    ],
)
def test_status_jump_backward_rejected(
    db_session, current: ComplaintStatusEnum, target: ComplaintStatusEnum
) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile, status=current)

    with pytest.raises(ValueError, match="invalid complaint status transition"):
        service(db_session).update_complaint(
            owner, complaint.id, ComplaintUpdate(status=target)
        )


@pytest.mark.parametrize(
    "target",
    [
        ComplaintStatusEnum.OPEN,
        ComplaintStatusEnum.IN_PROGRESS,
        ComplaintStatusEnum.ON_HOLD,
        ComplaintStatusEnum.RESOLVED,
    ],
)
def test_closed_is_terminal(
    db_session, target: ComplaintStatusEnum
) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(
        db_session, org, prop, profile, status=ComplaintStatusEnum.CLOSED
    )

    with pytest.raises(ValueError, match="a closed complaint cannot be reopened"):
        service(db_session).update_complaint(
            owner, complaint.id, ComplaintUpdate(status=target)
        )


def test_closed_no_op_is_allowed(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(
        db_session, org, prop, profile, status=ComplaintStatusEnum.CLOSED
    )

    updated = service(db_session).update_complaint(
        owner, complaint.id, ComplaintUpdate(status=ComplaintStatusEnum.CLOSED)
    )
    assert updated.status == ComplaintStatusEnum.CLOSED


def test_rejected_transition_leaves_row_unchanged(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    with pytest.raises(ValueError):
        service(db_session).update_complaint(
            owner, complaint.id, ComplaintUpdate(status=ComplaintStatusEnum.CLOSED)
        )

    db_session.expire_all()
    assert ComplaintRepository(db_session).get_by_id(complaint.id).status == (
        ComplaintStatusEnum.OPEN
    )
