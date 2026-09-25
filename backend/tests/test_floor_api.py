"""End-to-end floor API tests: auth, org-role authorization, field integrity."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.enums import OrganizationRoleEnum, PropertyTypeEnum, RoleEnum
from app.repositories.building import BuildingRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.schemas.building import BuildingCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate


def seed_org_with_building(
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
        building = BuildingRepository(session).create(
            BuildingCreate(name="Block A", organization_id=org.id, property_id=prop.id),
        )
    return org, building


def owner(api_app, *, email: str = "owner@example.com"):
    return seed_org_with_building(
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


def create_payload(
    org, building, *, floor_number: int = 0, name: str = "Ground", extra: dict | None = None
) -> dict:
    body = {
        "organization_id": str(org.id),
        "building_id": str(building.id),
        "floor_number": floor_number,
        "name": name,
    }
    if extra:
        body.update(extra)
    return body


def create_floor(
    api_app,
    make_token,
    org,
    building,
    *,
    email: str = "owner@example.com",
    floor_number: int = 0,
    name: str = "Ground",
) -> dict:
    headers = auth(api_app.client, make_token, email=email)
    r = api_app.client.post(
        "/api/v1/floors",
        headers=headers,
        json=create_payload(org, building, floor_number=floor_number, name=name),
    )
    assert r.status_code == 201
    return r.json()


def test_post_floors_owner_created(api_app, make_token) -> None:
    org, building = owner(api_app)

    r = api_app.client.post(
        "/api/v1/floors",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json=create_payload(org, building),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["building_id"] == str(building.id)
    assert body["floor_number"] == 0
    assert body["name"] == "Ground"


def test_post_floors_duplicate_conflict(api_app, make_token) -> None:
    org, building = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    first = api_app.client.post(
        "/api/v1/floors",
        headers=headers,
        json=create_payload(org, building),
    )
    assert first.status_code == 201

    r = api_app.client.post(
        "/api/v1/floors",
        headers=headers,
        json=create_payload(org, building),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "floor already exists"


def test_post_floors_staff_forbidden(api_app, make_token) -> None:
    org, building = seed_org_with_building(
        api_app,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        member_role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.post(
        "/api/v1/floors",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json=create_payload(org, building),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_get_floors_member_sees_building(api_app, make_token) -> None:
    org, building = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    api_app.client.post(
        "/api/v1/floors",
        headers=headers,
        json=create_payload(org, building, floor_number=1, name="First"),
    )

    r = api_app.client.get(
        "/api/v1/floors",
        headers=headers,
        params={"organization_id": str(org.id), "building_id": str(building.id)},
    )
    assert r.status_code == 200
    assert r.json()[0]["name"] == "First"


def test_get_floors_non_member_forbidden(api_app, make_token) -> None:
    org, building = owner(api_app)
    api_app.seed(email="outsider@example.com", role=RoleEnum.TENANT)

    r = api_app.client.get(
        "/api/v1/floors",
        headers=auth(api_app.client, make_token, email="outsider@example.com"),
        params={"organization_id": str(org.id), "building_id": str(building.id)},
    )
    assert r.status_code == 403


def test_get_floor_member_succeeds(api_app, make_token) -> None:
    org, building = owner(api_app)
    created = create_floor(api_app, make_token, org, building)

    r = api_app.client.get(
        f"/api/v1/floors/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_floor_missing_not_found(api_app, make_token) -> None:
    owner(api_app)

    r = api_app.client.get(
        f"/api/v1/floors/{uuid4()}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "floor not found"


def test_patch_floor_owner_updates_fields(api_app, make_token) -> None:
    org, building = owner(api_app)
    created = create_floor(api_app, make_token, org, building)

    r = api_app.client.patch(
        f"/api/v1/floors/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json={"floor_number": 1, "name": "  First  "},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["floor_number"] == 1
    assert body["name"] == "First"
    assert body["organization_id"] == str(org.id)
    assert body["building_id"] == str(building.id)


def test_patch_floor_duplicate_number_conflict(api_app, make_token) -> None:
    org, building = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    create_floor(api_app, make_token, org, building, floor_number=1, name="First")
    ground = create_floor(api_app, make_token, org, building, floor_number=0, name="Ground")

    r = api_app.client.patch(
        f"/api/v1/floors/{ground['id']}",
        headers=headers,
        json={"floor_number": 1},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "floor already exists"


def test_patch_floor_staff_forbidden(api_app, make_token) -> None:
    org, building = owner(api_app)
    seed_member(
        api_app,
        org,
        email="staff@example.com",
        member_role=OrganizationRoleEnum.STAFF,
    )
    created = create_floor(api_app, make_token, org, building)

    r = api_app.client.patch(
        f"/api/v1/floors/{created['id']}",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json={"name": "Nope"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"