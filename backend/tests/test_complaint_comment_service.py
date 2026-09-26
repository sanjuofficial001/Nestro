"""Service-layer complaint comments: parent-complaint authorization, authorship, and
the `is_internal` pass-through."""

from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.complaint import Complaint
from app.models.enums import (
    ComplaintCategoryEnum,
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
)
from app.models.organization import Organization
from app.models.property import Property
from app.models.resident_profile import ResidentProfile
from app.models.user import User
from app.repositories.complaint import ComplaintRepository
from app.repositories.complaint_comment import ComplaintCommentRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.user import UserRepository
from app.schemas.complaint import ComplaintCreate
from app.schemas.complaint_comment import ComplaintCommentCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.user import UserCreate
from app.services.complaint_comment_service import ComplaintCommentService


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
) -> None:
    OrganizationMemberRepository(db_session).create(
        OrganizationMemberCreate(organization_id=org.id, user_id=user.id, role=role),
    )


def make_property(db_session, org) -> Property:
    return PropertyRepository(db_session).create(
        PropertyCreate(
            name="PSG Boys PG",
            property_type=PropertyTypeEnum.PG,
            organization_id=org.id,
        ),
    )


def make_profile(db_session, org, prop) -> ResidentProfile:
    resident = make_user(db_session, role=RoleEnum.TENANT)
    make_member(db_session, org, resident)
    member = OrganizationMemberRepository(db_session).get_for_user(resident.id)[0]
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


def seed_org(db_session, *, slug: str = "abc-pg"):
    org = make_org(db_session, slug=slug)
    prop = make_property(db_session, org)
    profile = make_profile(db_session, org, prop)
    owner = make_user(db_session, role=RoleEnum.PG_OWNER)
    make_member(db_session, org, owner, role=OrganizationRoleEnum.OWNER)
    return org, owner, prop, profile


def make_complaint(db_session, org, prop, profile) -> Complaint:
    return ComplaintRepository(db_session).create(
        ComplaintCreate(
            organization_id=org.id,
            property_id=prop.id,
            resident_profile_id=profile.id,
            title="Tap leaking",
            description="The bathroom tap drips constantly.",
            category=ComplaintCategoryEnum.PLUMBING,
        ),
    )


def service(db_session) -> ComplaintCommentService:
    return ComplaintCommentService(db_session)


def seed_caller(db_session, org, *, role: RoleEnum, member_role: OrganizationRoleEnum):
    user = make_user(db_session, role=role)
    make_member(db_session, org, user, role=member_role)
    return user


# --- create -----------------------------------------------------------------


def test_create_comment_owner_succeeds(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    comment = service(db_session).create_comment(
        owner, complaint.id, ComplaintCommentCreate(body="Plumber booked.")
    )
    assert comment.id is not None
    assert comment.complaint_id == complaint.id
    assert comment.comment == "Plumber booked."
    assert comment.is_internal is False
    assert comment.created_at is not None


@pytest.mark.parametrize("member_role", list(OrganizationRoleEnum))
def test_every_org_role_may_post(db_session, member_role: OrganizationRoleEnum) -> None:
    """OWNER, MANAGER and STAFF all post — decision 5/6."""
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    caller = seed_caller(
        db_session,
        org,
        role=RoleEnum.STAFF,
        member_role=member_role,
    )

    comment = service(db_session).create_comment(
        caller, complaint.id, ComplaintCommentCreate(body="Looking into it.")
    )
    assert comment.user_id == caller.id


def test_create_comment_manager_succeeds(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    manager = seed_caller(
        db_session,
        org,
        role=RoleEnum.MANAGER,
        member_role=OrganizationRoleEnum.MANAGER,
    )

    comment = service(db_session).create_comment(
        manager, complaint.id, ComplaintCommentCreate(body="Vendor called.")
    )
    assert comment.user_id == manager.id


def test_create_comment_super_admin_bypasses(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    admin = make_user(db_session, role=RoleEnum.SUPER_ADMIN)

    comment = service(db_session).create_comment(
        admin, complaint.id, ComplaintCommentCreate(body="Reviewed.")
    )
    assert comment.user_id == admin.id


def test_create_comment_non_member_denied(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_comment(
            outsider, complaint.id, ComplaintCommentCreate(body="x")
        )


def test_create_comment_unknown_complaint_not_found(db_session) -> None:
    _, owner, _, _ = seed_org(db_session)

    with pytest.raises(NotFoundError, match="complaint not found"):
        service(db_session).create_comment(
            owner, uuid4(), ComplaintCommentCreate(body="x")
        )


def test_create_comment_foreign_org_complaint_denied(db_session) -> None:
    """The parent complaint is the tenant boundary. A caller who is not a member of
    the complaint's organization is refused by `ComplaintService.get_complaint` with
    403 — the same answer the shipped complaint endpoints give (see the
    existence-oracle note in the phase report)."""
    _, owner, _, _ = seed_org(db_session, slug="abc-pg")
    other_org = make_org(db_session, slug="zzz-pg")
    other_prop = make_property(db_session, other_org)
    other_profile = make_profile(db_session, other_org, other_prop)
    foreign = make_complaint(db_session, other_org, other_prop, other_profile)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).create_comment(
            owner, foreign.id, ComplaintCommentCreate(body="x")
        )


def test_create_comment_authorship_comes_from_the_caller(db_session) -> None:
    """`user_id` is never taken from the payload — the schema forbids it, and the
    service reads it off the authenticated user."""
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    comment = service(db_session).create_comment(
        owner, complaint.id, ComplaintCommentCreate(body="Mine.")
    )
    assert comment.user_id == owner.id


def test_create_comment_is_internal_round_trips(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    comment = service(db_session).create_comment(
        owner,
        complaint.id,
        ComplaintCommentCreate(body="Quote is 4k, hold till month end.", is_internal=True),
    )
    db_session.expire_all()
    assert ComplaintCommentRepository(db_session).get_by_id(comment.id).is_internal is True


def test_create_comment_strips_body(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)

    comment = service(db_session).create_comment(
        owner, complaint.id, ComplaintCommentCreate(body="  Plumber booked.  ")
    )
    assert comment.comment == "Plumber booked."


# --- list -------------------------------------------------------------------


def test_list_comments_returns_the_thread(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    repo = ComplaintCommentRepository(db_session)
    repo.create(complaint_id=complaint.id, user_id=owner.id, body="first", is_internal=False)
    second = repo.create(
        complaint_id=complaint.id, user_id=owner.id, body="second", is_internal=False
    )

    found = service(db_session).list_comments(owner, complaint.id)
    assert [c.comment for c in found] == ["first", "second"]
    assert found[-1] == second


def test_list_comments_empty_thread(db_session) -> None:
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    assert service(db_session).list_comments(owner, complaint.id) == []


def test_list_comments_includes_internal_for_members(db_session) -> None:
    """Deferred-filter note: internal notes are returned to every org member today.
    This test documents current behaviour, not a permanent rule."""
    org, owner, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    ComplaintCommentRepository(db_session).create(
        complaint_id=complaint.id,
        user_id=owner.id,
        body="internal note",
        is_internal=True,
    )

    found = service(db_session).list_comments(owner, complaint.id)
    assert [c.comment for c in found] == ["internal note"]


def test_list_comments_staff_may_read(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    staff = seed_caller(
        db_session, org, role=RoleEnum.STAFF, member_role=OrganizationRoleEnum.STAFF
    )
    ComplaintCommentRepository(db_session).create(
        complaint_id=complaint.id, user_id=staff.id, body="ack", is_internal=False
    )

    assert len(service(db_session).list_comments(staff, complaint.id)) == 1


def test_list_comments_non_member_denied(db_session) -> None:
    org, _, prop, profile = seed_org(db_session)
    complaint = make_complaint(db_session, org, prop, profile)
    outsider = make_user(db_session, role=RoleEnum.PG_OWNER)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_comments(outsider, complaint.id)


def test_list_comments_unknown_complaint_not_found(db_session) -> None:
    _, owner, _, _ = seed_org(db_session)
    with pytest.raises(NotFoundError, match="complaint not found"):
        service(db_session).list_comments(owner, uuid4())


def test_list_comments_foreign_org_complaint_denied(db_session) -> None:
    _, owner, _, _ = seed_org(db_session, slug="abc-pg")
    other_org = make_org(db_session, slug="zzz-pg")
    other_prop = make_property(db_session, other_org)
    other_profile = make_profile(db_session, other_org, other_prop)
    foreign = make_complaint(db_session, other_org, other_prop, other_profile)

    with pytest.raises(PermissionError, match="insufficient permissions"):
        service(db_session).list_comments(owner, foreign.id)
