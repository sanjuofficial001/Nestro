"""End-to-end complaint comment API tests: auth, org authorization, thread shape."""

from uuid import uuid4

from app.models.enums import (
    ComplaintCategoryEnum,
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
                organization_id=org.id, user_id=user.id, role=member_role
            ),
        )
        resident = api_app.seed(
            email=f"resident-{uuid4().hex[:8]}@example.com", role=RoleEnum.TENANT
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
        OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(organization_id=org.id, user_id=user.id, role=role),
        )
    return user


def seed_outsider(api_app, *, email: str = "outsider@example.com") -> str:
    """A real user in a different org, so the request is refused by authorization
    (403) rather than failing authentication (401)."""
    api_app.seed(email=email, role=RoleEnum.PG_OWNER)
    with api_app.factory() as session:
        other = OrganizationRepository(session).create(
            OrganizationCreate(name="ZZZ PG", slug=f"zzz-pg-{uuid4().hex[:8]}"),
        )
        user = UserRepository(session).get_by_email(email)
        OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=other.id, user_id=user.id, role=OrganizationRoleEnum.OWNER
            ),
        )
    return email


def auth(make_token, *, email: str = "owner@example.com") -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def make_complaint(api_app, org, prop, profile) -> str:
    with api_app.factory() as session:
        complaint = ComplaintRepository(session).create(
            ComplaintCreate(
                organization_id=org.id,
                property_id=prop.id,
                resident_profile_id=profile.id,
                title="Tap leaking",
                description="The bathroom tap drips constantly.",
                category=ComplaintCategoryEnum.PLUMBING,
            ),
        )
        return str(complaint.id)


def post_comment(api_app, make_token, complaint_id: str, **overrides) -> dict:
    body = {"body": "Plumber booked."}
    body.update(overrides)
    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token),
        json=body,
    )
    assert r.status_code == 201, r.json()
    return r.json()


# --- auth -------------------------------------------------------------------


def test_get_comments_requires_auth(api_app) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    r = api_app.client.get(f"{BASE}/{complaint_id}/comments")
    assert r.status_code == 401


def test_post_comments_requires_auth(api_app) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    r = api_app.client.post(f"{BASE}/{complaint_id}/comments", json={"body": "x"})
    assert r.status_code == 401


# --- create -----------------------------------------------------------------


def test_post_comment_created(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    body = post_comment(api_app, make_token, complaint_id)
    assert set(body) == {
        "id",
        "complaint_id",
        "user_id",
        "body",
        "is_internal",
        "created_at",
    }
    assert body["body"] == "Plumber booked."
    assert body["complaint_id"] == complaint_id
    assert body["is_internal"] is False
    assert body["created_at"]


def test_post_comment_response_uses_body_not_comment(api_app, make_token) -> None:
    """The wire name is `body`; the column is `comment` and must not leak out."""
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    body = post_comment(api_app, make_token, complaint_id)
    assert "comment" not in body
    assert "body" in body


def test_post_comment_strips_whitespace(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    body = post_comment(api_app, make_token, complaint_id, body="  Plumber booked.  ")
    assert body["body"] == "Plumber booked."


def test_post_comment_is_internal_round_trips(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    body = post_comment(
        api_app, make_token, complaint_id, is_internal=True, body="Quote is 4k."
    )
    assert body["is_internal"] is True

    listed = api_app.client.get(
        f"{BASE}/{complaint_id}/comments", headers=auth(make_token)
    ).json()
    assert [c["is_internal"] for c in listed] == [True]


def test_post_comment_staff_allowed(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    seed_member(
        api_app,
        org,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token, email="staff@example.com"),
        json={"body": "Looking into it."},
    )
    assert r.status_code == 201


def test_post_comment_manager_allowed(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    seed_member(
        api_app,
        org,
        email="manager@example.com",
        user_role=RoleEnum.MANAGER,
        role=OrganizationRoleEnum.MANAGER,
    )

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token, email="manager@example.com"),
        json={"body": "Vendor called."},
    )
    assert r.status_code == 201


def test_post_comment_non_member_forbidden(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    outsider = seed_outsider(api_app)

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token, email=outsider),
        json={"body": "x"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_post_comment_unknown_complaint_not_found(api_app, make_token) -> None:
    owner(api_app)
    r = api_app.client.post(
        f"{BASE}/{uuid4()}/comments", headers=auth(make_token), json={"body": "x"}
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "complaint not found"


def test_post_comment_blank_body_unprocessable(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments", headers=auth(make_token), json={"body": "   "}
    )
    assert r.status_code == 422


def test_post_comment_body_too_long_unprocessable(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token),
        json={"body": "x" * 2001},
    )
    assert r.status_code == 422


def test_post_comment_body_exactly_2000_accepted(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    body = post_comment(api_app, make_token, complaint_id, body="x" * 2000)
    assert len(body["body"]) == 2000


def test_post_comment_rejects_complaint_id_in_body(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token),
        json={"body": "x", "complaint_id": str(uuid4())},
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "extra_forbidden"


def test_post_comment_rejects_user_id_in_body(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token),
        json={"body": "x", "user_id": str(uuid4())},
    )
    assert r.status_code == 422


def test_post_comment_rejects_updated_at(api_app, make_token) -> None:
    """Comments are immutable — there is no `updated_at` to set."""
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    r = api_app.client.post(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token),
        json={"body": "x", "updated_at": "2026-01-01T00:00:00Z"},
    )
    assert r.status_code == 422


# --- list -------------------------------------------------------------------


def test_get_comments_empty_thread(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)

    r = api_app.client.get(f"{BASE}/{complaint_id}/comments", headers=auth(make_token))
    assert r.status_code == 200
    assert r.json() == []


def test_get_comments_returns_thread(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    first = post_comment(api_app, make_token, complaint_id, body="first")
    second = post_comment(api_app, make_token, complaint_id, body="second")

    r = api_app.client.get(f"{BASE}/{complaint_id}/comments", headers=auth(make_token))
    assert r.status_code == 200
    assert [c["body"] for c in r.json()] == ["first", "second"]
    assert [c["id"] for c in r.json()] == [first["id"], second["id"]]


def test_get_comments_scoped_to_that_complaint(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    mine = make_complaint(api_app, org, prop, profile)
    other = make_complaint(api_app, org, prop, profile)
    post_comment(api_app, make_token, mine, body="mine")
    post_comment(api_app, make_token, other, body="theirs")

    r = api_app.client.get(f"{BASE}/{mine}/comments", headers=auth(make_token))
    assert [c["body"] for c in r.json()] == ["mine"]


def test_get_comments_staff_allowed(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    post_comment(api_app, make_token, complaint_id)
    seed_member(
        api_app,
        org,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.get(
        f"{BASE}/{complaint_id}/comments",
        headers=auth(make_token, email="staff@example.com"),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_comments_non_member_forbidden(api_app, make_token) -> None:
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    outsider = seed_outsider(api_app)

    r = api_app.client.get(
        f"{BASE}/{complaint_id}/comments", headers=auth(make_token, email=outsider)
    )
    assert r.status_code == 403


def test_get_comments_unknown_complaint_not_found(api_app, make_token) -> None:
    owner(api_app)
    r = api_app.client.get(f"{BASE}/{uuid4()}/comments", headers=auth(make_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "complaint not found"


# --- immutability -----------------------------------------------------------


def test_comment_has_no_update_or_delete_endpoint(api_app, make_token) -> None:
    """Comments are immutable, so the thread exposes POST and GET only."""
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    created = post_comment(api_app, make_token, complaint_id)

    # No route is registered for a single comment, so this is a 404 path miss
    # (a 405 would mean the path exists and only the method is wrong).
    patch = api_app.client.patch(
        f"{BASE}/{complaint_id}/comments/{created['id']}",
        headers=auth(make_token),
        json={"body": "edited"},
    )
    assert patch.status_code == 404

    delete = api_app.client.delete(
        f"{BASE}/{complaint_id}/comments/{created['id']}", headers=auth(make_token)
    )
    assert delete.status_code == 404

    # and the original text is untouched
    r = api_app.client.get(f"{BASE}/{complaint_id}/comments", headers=auth(make_token))
    assert [c["body"] for c in r.json()] == ["Plumber booked."]


def test_complaint_read_shape_unchanged(api_app, make_token) -> None:
    """Decision: comments are a separate endpoint, so `ComplaintRead` did not grow a
    `comments` field."""
    org, prop, profile = owner(api_app)
    complaint_id = make_complaint(api_app, org, prop, profile)
    post_comment(api_app, make_token, complaint_id)

    r = api_app.client.get(f"{BASE}/{complaint_id}", headers=auth(make_token))
    assert r.status_code == 200
    assert "comments" not in r.json()
