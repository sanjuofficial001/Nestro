"""End-to-end property API tests: auth, org-role authorization, field integrity."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.enums import OrganizationRoleEnum, RoleEnum
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate


def seed_membership(
    api_app,
    *,
    email: str,
    user_role: RoleEnum,
    member_role: OrganizationRoleEnum,
    org=None,
):
    user = api_app.seed(email=email, role=user_role)
    with api_app.factory() as session:
        if org is None:
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
    return org


def owner(api_app, *, email: str = "owner@example.com"):
    return seed_membership(
        api_app,
        email=email,
        user_role=RoleEnum.PG_OWNER,
        member_role=OrganizationRoleEnum.OWNER,
    )


def auth(client: TestClient, make_token, *, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def create_payload(org, *, name: str = "PSG Boys PG", extra: dict | None = None) -> dict:
    body = {"organization_id": str(org.id), "name": name, "property_type": "PG"}
    if extra:
        body.update(extra)
    return body


def create_property(
    api_app,
    make_token,
    org,
    *,
    email: str = "owner@example.com",
    name: str = "PSG Boys PG",
) -> dict:
    headers = auth(api_app.client, make_token, email=email)
    r = api_app.client.post(
        "/api/v1/properties",
        headers=headers,
        json=create_payload(org, name=name),
    )
    assert r.status_code == 201
    return r.json()


def test_post_properties_owner_created(api_app, make_token) -> None:
    org = owner(api_app)

    r = api_app.client.post(
        "/api/v1/properties",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json=create_payload(org),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["name"] == "PSG Boys PG"
    assert body["property_type"] == "PG"


def test_post_properties_manager_created(api_app, make_token) -> None:
    org = seed_membership(
        api_app,
        email="manager@example.com",
        user_role=RoleEnum.MANAGER,
        member_role=OrganizationRoleEnum.MANAGER,
    )

    r = api_app.client.post(
        "/api/v1/properties",
        headers=auth(api_app.client, make_token, email="manager@example.com"),
        json=create_payload(org),
    )
    assert r.status_code == 201


def test_post_properties_staff_forbidden(api_app, make_token) -> None:
    org = seed_membership(
        api_app,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        member_role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.post(
        "/api/v1/properties",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json=create_payload(org),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_post_properties_duplicate_conflict(api_app, make_token) -> None:
    org = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    first = api_app.client.post(
        "/api/v1/properties",
        headers=headers,
        json=create_payload(org),
    )
    assert first.status_code == 201

    r = api_app.client.post("/api/v1/properties", headers=headers, json=create_payload(org))
    assert r.status_code == 409
    assert r.json()["detail"] == "property already exists"


def test_get_properties_member_sees_org(api_app, make_token) -> None:
    org = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    api_app.client.post(
        "/api/v1/properties",
        headers=headers,
        json=create_payload(org, name="Sunrise Apartments"),
    )

    r = api_app.client.get(
        "/api/v1/properties",
        headers=headers,
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 200
    assert r.json()[0]["name"] == "Sunrise Apartments"


def test_get_properties_non_member_forbidden(api_app, make_token) -> None:
    org = owner(api_app)
    api_app.seed(email="outsider@example.com", role=RoleEnum.TENANT)

    r = api_app.client.get(
        "/api/v1/properties",
        headers=auth(api_app.client, make_token, email="outsider@example.com"),
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 403


def test_get_property_member_succeeds(api_app, make_token) -> None:
    org = owner(api_app)
    created = create_property(api_app, make_token, org)

    r = api_app.client.get(
        f"/api/v1/properties/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_property_non_member_forbidden(api_app, make_token) -> None:
    org = owner(api_app)
    created = create_property(api_app, make_token, org)
    api_app.seed(email="outsider@example.com", role=RoleEnum.TENANT)

    r = api_app.client.get(
        f"/api/v1/properties/{created['id']}",
        headers=auth(api_app.client, make_token, email="outsider@example.com"),
    )
    assert r.status_code == 403


def test_get_property_missing_not_found(api_app, make_token) -> None:
    owner(api_app)

    r = api_app.client.get(
        f"/api/v1/properties/{uuid4()}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "property not found"


def test_patch_property_owner_updates_fields(api_app, make_token) -> None:
    org = owner(api_app)
    created = create_property(api_app, make_token, org)

    r = api_app.client.patch(
        f"/api/v1/properties/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json={
            "name": "  PSG Boys Renamed  ",
            "status": "INACTIVE",
            "address": "Gandhi St, Chennai",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "PSG Boys Renamed"
    assert body["status"] == "INACTIVE"
    assert body["address"] == "Gandhi St, Chennai"
    assert body["organization_id"] == str(org.id)
    assert body["property_type"] == "PG"


def test_patch_property_manager_succeeds(api_app, make_token) -> None:
    org = seed_membership(
        api_app,
        email="manager@example.com",
        user_role=RoleEnum.MANAGER,
        member_role=OrganizationRoleEnum.MANAGER,
    )
    created = create_property(api_app, make_token, org, email="manager@example.com")

    r = api_app.client.patch(
        f"/api/v1/properties/{created['id']}",
        headers=auth(api_app.client, make_token, email="manager@example.com"),
        json={"rules": "No visitors after 10pm"},
    )
    assert r.status_code == 200
    assert r.json()["rules"] == "No visitors after 10pm"


def test_patch_property_staff_forbidden(api_app, make_token) -> None:
    org = owner(api_app)
    seed_membership(
        api_app,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        member_role=OrganizationRoleEnum.STAFF,
        org=org,
    )
    created = create_property(api_app, make_token, org)

    r = api_app.client.patch(
        f"/api/v1/properties/{created['id']}",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json={"name": "Nope"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"