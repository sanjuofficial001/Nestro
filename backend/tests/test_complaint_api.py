"""End-to-end complaint API tests: auth, org-role authorization, and the
status lifecycle over HTTP."""

from uuid import uuid4

from app.models.enums import (
    ComplaintCategoryEnum,
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

BASE = "/api/v1/complaints"


def seed_org(api_app, *, email: str, user_role: RoleEnum, member_role: OrganizationRoleEnum):
    user = api_app.seed(email=email, role=user_role)
    with api_app.factory() as session:
        org = OrganizationRepository(session).create(
            OrganizationCreate(name="ABC PG", slug=f"abc-pg-{uuid4().hex[:8]}"),
        )
        OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=org.id,
                user_id=user.id,
                role=member_role,
            ),
        )
        resident = api_app.seed(
            email=f"resident-{uuid4().hex[:8]}@example.com",
            role=RoleEnum.TENANT,
        )
        member = OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=org.id,
                user_id=resident.id,
                role=OrganizationRoleEnum.STAFF,
            ),
        )
        prop = PropertyRepository(session).create(
            PropertyCreate(
                name="PSG Boys PG",
                property_type=PropertyTypeEnum.PG,
                organization_id=org.id,
            ),
        )
        profile = ResidentProfileRepository(session).create(
            ResidentProfileCreate(
                organization_id=org.id,
                organization_member_id=member.id,
                property_id=prop.id,
                emergency_contact_name="Asha Rao",
                emergency_contact_phone="9876543210",
                address="12 MG Road",
            ),
        )
    return org, prop, profile


def owner(api_app, *, email: str = "owner@example.com"):
    return seed_org(
        api_app,
        email=email,
        user_role=RoleEnum.PG_OWNER,
        member_role=OrganizationRoleEnum.OWNER,
    )


def seed_member(api_app, org, *, email: str, user_role: RoleEnum, role: OrganizationRoleEnum):
    user = api_app.seed(email=email, role=user_role)
    with api_app.factory() as session:
        member = OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=org.id,
                user_id=user.id,
                role=role,
            ),
        )
    return user, member


def seed_outsider(api_app, *, email: str = "outsider@example.com") -> str:
    """A real user who belongs to a different org: the token resolves, so the request
    is refused by authorization (403) rather than by authentication (401)."""
    api_app.seed(email=email, role=RoleEnum.PG_OWNER)
    with api_app.factory() as session:
        other = OrganizationRepository(session).create(
            OrganizationCreate(name="ZZZ PG", slug=f"zzz-pg-{uuid4().hex[:8]}"),
        )
        user = UserRepository(session).get_by_email(email)
        OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=other.id,
                user_id=user.id,
                role=OrganizationRoleEnum.OWNER,
            ),
        )
    return email


def auth(make_token, *, email: str = "owner@example.com") -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def payload(org, prop, profile, **overrides) -> dict:
    body = {
        "organization_id": str(org.id),
        "property_id": str(prop.id),
        "resident_profile_id": str(profile.id),
        "title": "Tap leaking",
        "description": "The bathroom tap drips constantly.",
        "category": "PLUMBING",
    }
    body.update(overrides)
    return body


def create_complaint(api_app, make_token, org, prop, profile, **overrides) -> dict:
    r = api_app.client.post(
        BASE,
        headers=auth(make_token),
        json=payload(org, prop, profile, **overrides),
    )
    assert r.status_code == 201, r.json()
    return r.json()


def make_row(api_app, org, prop, profile, **overrides) -> dict:
    with api_app.factory() as session:
        complaint = ComplaintRepository(session).create(
            ComplaintCreate(
                organization_id=org.id,
                property_id=prop.id,
                resident_profile_id=profile.id,
                title=overrides.pop("title", "Tap leaking"),
                description="The bathroom tap drips constantly.",
                category=ComplaintCategoryEnum.PLUMBING,
                **overrides,
            ),
        )
        return {"id": str(complaint.id)}


# --- auth -------------------------------------------------------------------


def test_post_complaints_requires_auth(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    r = api_app.client.post(BASE, json=payload(org, prop, profile))
    assert r.status_code == 401


def test_get_complaints_requires_auth(api_app) -> None:
    org, _, _ = owner(api_app)
    r = api_app.client.get(BASE, params={"organization_id": str(org.id)})
    assert r.status_code == 401


# --- create -----------------------------------------------------------------


def test_post_complaints_owner_created(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)

    r = api_app.client.post(
        BASE, headers=auth(make_token), json=payload(org, prop, profile)
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["property_id"] == str(prop.id)
    assert body["resident_profile_id"] == str(profile.id)
    assert body["title"] == "Tap leaking"
    assert body["category"] == "PLUMBING"
    assert body["priority"] == "MEDIUM"
    assert body["status"] == "OPEN"
    assert body["assigned_to_member_id"] is None
    assert body["resolved_at"] is None


def test_post_complaints_manager_created(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    seed_member(
        api_app,
        org,
        email="manager@example.com",
        user_role=RoleEnum.MANAGER,
        role=OrganizationRoleEnum.MANAGER,
    )

    r = api_app.client.post(
        BASE,
        headers=auth(make_token, email="manager@example.com"),
        json=payload(org, prop, profile),
    )
    assert r.status_code == 201


def test_post_complaints_staff_forbidden(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    seed_member(
        api_app,
        org,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.post(
        BASE,
        headers=auth(make_token, email="staff@example.com"),
        json=payload(org, prop, profile),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_post_complaints_non_member_forbidden(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    outsider = seed_outsider(api_app)

    r = api_app.client.post(
        BASE,
        headers=auth(make_token, email=outsider),
        json=payload(org, prop, profile),
    )
    assert r.status_code == 403


def test_post_complaints_unknown_property_not_found(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)

    r = api_app.client.post(
        BASE,
        headers=auth(make_token),
        json=payload(org, prop, profile, property_id=str(uuid4())),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "property not found"


def test_post_complaints_unknown_resident_not_found(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)

    r = api_app.client.post(
        BASE,
        headers=auth(make_token),
        json=payload(org, prop, profile, resident_profile_id=str(uuid4())),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "resident profile not found"


def test_post_complaints_foreign_property_conflict(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    with api_app.factory() as session:
        other = OrganizationRepository(session).create(
            OrganizationCreate(name="ZZZ PG", slug=f"zzz-pg-{uuid4().hex[:8]}"),
        )
        foreign_prop = PropertyRepository(session).create(
            PropertyCreate(
                name="Annex PG",
                property_type=PropertyTypeEnum.PG,
                organization_id=other.id,
            ),
        )

    r = api_app.client.post(
        BASE,
        headers=auth(make_token),
        json=payload(org, prop, profile, property_id=str(foreign_prop.id)),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "property does not belong to this organization"


def test_post_complaints_title_too_long_unprocessable(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)

    r = api_app.client.post(
        BASE, headers=auth(make_token), json=payload(org, prop, profile, title="x" * 201)
    )
    assert r.status_code == 422


def test_post_complaints_description_too_long_unprocessable(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)

    r = api_app.client.post(
        BASE,
        headers=auth(make_token),
        json=payload(org, prop, profile, description="x" * 2001),
    )
    assert r.status_code == 422


def test_post_complaints_unknown_category_unprocessable(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)

    r = api_app.client.post(
        BASE,
        headers=auth(make_token),
        json=payload(org, prop, profile, category="NOT_A_CATEGORY"),
    )
    assert r.status_code == 422


def test_post_complaints_strips_whitespace(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)

    r = api_app.client.post(
        BASE,
        headers=auth(make_token),
        json=payload(org, prop, profile, title="  Tap leaking  "),
    )
    assert r.status_code == 201
    assert r.json()["title"] == "Tap leaking"


# --- list -------------------------------------------------------------------


def test_get_complaints_lists_org_complaints(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.get(
        BASE, headers=auth(make_token), params={"organization_id": str(org.id)}
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_complaints_requires_organization_id(api_app, make_token) -> None:
    owner(api_app)
    r = api_app.client.get(BASE, headers=auth(make_token))
    assert r.status_code == 422


def test_get_complaints_non_member_forbidden(api_app, make_token) -> None:
    org, _, _ = owner(api_app)
    outsider = seed_outsider(api_app)

    r = api_app.client.get(
        BASE,
        headers=auth(make_token, email=outsider),
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 403


def test_get_complaints_staff_may_read(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    create_complaint(api_app, make_token, org, prop, profile)
    seed_member(
        api_app,
        org,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.get(
        BASE,
        headers=auth(make_token, email="staff@example.com"),
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_complaints_filters_by_status(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    create_complaint(api_app, make_token, org, prop, profile)
    target = create_complaint(
        api_app,
        make_token,
        org,
        prop,
        profile,
        title="Fan broken",
        status="IN_PROGRESS",
    )

    r = api_app.client.get(
        BASE,
        headers=auth(make_token),
        params={"organization_id": str(org.id), "status": "IN_PROGRESS"},
    )
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [target["id"]]


def test_get_complaints_filters_by_priority(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    create_complaint(api_app, make_token, org, prop, profile)
    target = create_complaint(
        api_app,
        make_token,
        org,
        prop,
        profile,
        title="Gas leak smell",
        priority="URGENT",
    )

    r = api_app.client.get(
        BASE,
        headers=auth(make_token),
        params={"organization_id": str(org.id), "priority": "URGENT"},
    )
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [target["id"]]


def test_get_complaints_filters_by_resident(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    mine = create_complaint(api_app, make_token, org, prop, profile)
    with api_app.factory() as session:
        resident = api_app.seed(
            email=f"other-{uuid4().hex[:8]}@example.com", role=RoleEnum.TENANT
        )
        other_member = OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=org.id,
                user_id=resident.id,
                role=OrganizationRoleEnum.STAFF,
            ),
        )
        other_profile = ResidentProfileRepository(session).create(
            ResidentProfileCreate(
                organization_id=org.id,
                organization_member_id=other_member.id,
                property_id=prop.id,
                emergency_contact_name="Asha Rao",
                emergency_contact_phone="9876543210",
                address="12 MG Road",
            ),
        )
    create_complaint(
        api_app, make_token, org, prop, other_profile, title="WiFi weak"
    )

    r = api_app.client.get(
        BASE,
        headers=auth(make_token),
        params={
            "organization_id": str(org.id),
            "resident_profile_id": str(profile.id),
        },
    )
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [mine["id"]]


def test_get_complaints_invalid_status_unprocessable(api_app, make_token) -> None:
    org, _, _ = owner(api_app)

    r = api_app.client.get(
        BASE,
        headers=auth(make_token),
        params={"organization_id": str(org.id), "status": "ESCALATED"},
    )
    assert r.status_code == 422


# --- get one ----------------------------------------------------------------


def test_get_complaint_by_id(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.get(f"{BASE}/{created['id']}", headers=auth(make_token))
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_complaint_by_id_unknown_not_found(api_app, make_token) -> None:
    owner(api_app)
    r = api_app.client.get(f"{BASE}/{uuid4()}", headers=auth(make_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "complaint not found"


def test_get_complaint_by_id_non_member_forbidden(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)
    outsider = seed_outsider(api_app)

    r = api_app.client.get(
        f"{BASE}/{created['id']}",
        headers=auth(make_token, email=outsider),
    )
    assert r.status_code == 403


# --- update -----------------------------------------------------------------


def test_patch_complaint_title(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"title": "Fan broken"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Fan broken"


def test_patch_complaint_priority(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"priority": "HIGH"},
    )
    assert r.status_code == 200
    assert r.json()["priority"] == "HIGH"


def test_patch_complaint_assignee(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)
    _, member = seed_member(
        api_app,
        org,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"assigned_to_member_id": str(member.id)},
    )
    assert r.status_code == 200
    assert r.json()["assigned_to_member_id"] == str(member.id)


def test_patch_complaint_category_rejected(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"category": "FOOD"},
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "extra_forbidden"


def test_patch_complaint_organization_id_rejected(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"organization_id": str(uuid4())},
    )
    assert r.status_code == 422


def test_patch_complaint_resolved_at_rejected(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"resolved_at": "2026-01-01T00:00:00Z"},
    )
    assert r.status_code == 422


def test_patch_complaint_staff_forbidden(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)
    seed_member(
        api_app,
        org,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token, email="staff@example.com"),
        json={"title": "Nope"},
    )
    assert r.status_code == 403


def test_patch_complaint_unknown_not_found(api_app, make_token) -> None:
    owner(api_app)
    r = api_app.client.patch(
        f"{BASE}/{uuid4()}", headers=auth(make_token), json={"title": "Nope"}
    )
    assert r.status_code == 404


def test_patch_complaint_status_one_step_forward(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"status": "IN_PROGRESS"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "IN_PROGRESS"


def test_patch_complaint_status_jump_conflict(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"status": "CLOSED"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "invalid complaint status transition"


def test_patch_complaint_closed_is_terminal(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    row = make_row(
        api_app, org, prop, profile, status=ComplaintStatusEnum.CLOSED
    )

    r = api_app.client.patch(
        f"{BASE}/{row['id']}",
        headers=auth(make_token),
        json={"status": "OPEN"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "a closed complaint cannot be reopened"


def test_patch_complaint_resolved_does_not_stamp_resolved_at(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    row = make_row(api_app, org, prop, profile, status=ComplaintStatusEnum.ON_HOLD)

    r = api_app.client.patch(
        f"{BASE}/{row['id']}",
        headers=auth(make_token),
        json={"status": "RESOLVED"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "RESOLVED"
    assert r.json()["resolved_at"] is None


def test_patch_complaint_title_too_long_unprocessable(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    created = create_complaint(api_app, make_token, org, prop, profile)

    r = api_app.client.patch(
        f"{BASE}/{created['id']}",
        headers=auth(make_token),
        json={"title": "x" * 201},
    )
    assert r.status_code == 422
