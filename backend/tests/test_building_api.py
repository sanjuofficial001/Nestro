"""End-to-end building API tests: auth, org-role authorization, field integrity."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.enums import OrganizationRoleEnum, PropertyTypeEnum, RoleEnum
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate


def seed_org_with_property(
    api_app,
    *,
    email: str,
    user_role: RoleEnum,
    member_role: OrganizationRoleEnum,
):
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
        prop = PropertyRepository(session).create(
            PropertyCreate(
                name="PSG Boys PG",
                property_type=PropertyTypeEnum.PG,
                organization_id=org.id,
            ),
        )
    return org, prop


def owner(api_app, *, email: str = "owner@example.com"):
    return seed_org_with_property(
        api_app,
        email=email,
        user_role=RoleEnum.PG_OWNER,
        member_role=OrganizationRoleEnum.OWNER,
    )


def seed_member(api_app, org, *, email: str, member_role: OrganizationRoleEnum) -> None:
    user = api_app.seed(email=email, role=RoleEnum.STAFF)
    with api_app.factory() as session:
        OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=org.id,
                user_id=user.id,
                role=member_role,
            ),
        )


def auth(client: TestClient, make_token, *, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def create_payload(org, prop, *, name: str = "Block A", extra: dict | None = None) -> dict:
    body = {"organization_id": str(org.id), "property_id": str(prop.id), "name": name}
    if extra:
        body.update(extra)
    return body


def create_building(
    api_app,
    make_token,
    org,
    prop,
    *,
    email: str = "owner@example.com",
    name: str = "Block A",
) -> dict:
    headers = auth(api_app.client, make_token, email=email)
    r = api_app.client.post(
        "/api/v1/buildings",
        headers=headers,
        json=create_payload(org, prop, name=name),
    )
    assert r.status_code == 201
    return r.json()


def test_post_buildings_owner_created(api_app, make_token) -> None:
    org, prop = owner(api_app)

    r = api_app.client.post(
        "/api/v1/buildings",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json=create_payload(org, prop),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["property_id"] == str(prop.id)
    assert body["name"] == "Block A"


def test_post_buildings_manager_created(api_app, make_token) -> None:
    org, prop = seed_org_with_property(
        api_app,
        email="manager@example.com",
        user_role=RoleEnum.MANAGER,
        member_role=OrganizationRoleEnum.MANAGER,
    )

    r = api_app.client.post(
        "/api/v1/buildings",
        headers=auth(api_app.client, make_token, email="manager@example.com"),
        json=create_payload(org, prop),
    )
    assert r.status_code == 201


def test_post_buildings_staff_forbidden(api_app, make_token) -> None:
    org, prop = seed_org_with_property(
        api_app,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        member_role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.post(
        "/api/v1/buildings",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json=create_payload(org, prop),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_post_buildings_duplicate_conflict(api_app, make_token) -> None:
    org, prop = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    first = api_app.client.post(
        "/api/v1/buildings",
        headers=headers,
        json=create_payload(org, prop),
    )
    assert first.status_code == 201

    r = api_app.client.post(
        "/api/v1/buildings",
        headers=headers,
        json=create_payload(org, prop),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "building already exists"


def test_get_buildings_member_sees_property(api_app, make_token) -> None:
    org, prop = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    api_app.client.post(
        "/api/v1/buildings",
        headers=headers,
        json=create_payload(org, prop, name="Annex"),
    )

    r = api_app.client.get(
        "/api/v1/buildings",
        headers=headers,
        params={"organization_id": str(org.id), "property_id": str(prop.id)},
    )
    assert r.status_code == 200
    assert r.json()[0]["name"] == "Annex"


def test_get_buildings_non_member_forbidden(api_app, make_token) -> None:
    org, prop = owner(api_app)
    api_app.seed(email="outsider@example.com", role=RoleEnum.TENANT)

    r = api_app.client.get(
        "/api/v1/buildings",
        headers=auth(api_app.client, make_token, email="outsider@example.com"),
        params={"organization_id": str(org.id), "property_id": str(prop.id)},
    )
    assert r.status_code == 403


def test_get_building_member_succeeds(api_app, make_token) -> None:
    org, prop = owner(api_app)
    created = create_building(api_app, make_token, org, prop)

    r = api_app.client.get(
        f"/api/v1/buildings/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_building_non_member_forbidden(api_app, make_token) -> None:
    org, prop = owner(api_app)
    created = create_building(api_app, make_token, org, prop)
    api_app.seed(email="outsider@example.com", role=RoleEnum.TENANT)

    r = api_app.client.get(
        f"/api/v1/buildings/{created['id']}",
        headers=auth(api_app.client, make_token, email="outsider@example.com"),
    )
    assert r.status_code == 403


def test_get_building_missing_not_found(api_app, make_token) -> None:
    owner(api_app)

    r = api_app.client.get(
        f"/api/v1/buildings/{uuid4()}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "building not found"


def test_patch_building_owner_updates_fields(api_app, make_token) -> None:
    org, prop = owner(api_app)
    created = create_building(api_app, make_token, org, prop)

    r = api_app.client.patch(
        f"/api/v1/buildings/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json={"name": "  Block A Renamed  ", "description": "North wing"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Block A Renamed"
    assert body["description"] == "North wing"
    assert body["organization_id"] == str(org.id)
    assert body["property_id"] == str(prop.id)


def test_patch_building_manager_succeeds(api_app, make_token) -> None:
    org, prop = seed_org_with_property(
        api_app,
        email="manager@example.com",
        user_role=RoleEnum.MANAGER,
        member_role=OrganizationRoleEnum.MANAGER,
    )
    created = create_building(api_app, make_token, org, prop, email="manager@example.com")

    r = api_app.client.patch(
        f"/api/v1/buildings/{created['id']}",
        headers=auth(api_app.client, make_token, email="manager@example.com"),
        json={"description": "East wing"},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "East wing"


def test_patch_building_staff_forbidden(api_app, make_token) -> None:
    org, prop = owner(api_app)
    seed_member(
        api_app,
        org,
        email="staff@example.com",
        member_role=OrganizationRoleEnum.STAFF,
    )
    created = create_building(api_app, make_token, org, prop)

    r = api_app.client.patch(
        f"/api/v1/buildings/{created['id']}",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json={"name": "Nope"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"