"""End-to-end room API tests: auth, org-role authorization, no capacity keys."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.enums import (
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
)
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate


def seed_org_with_floor(
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
        floor = FloorRepository(session).create(
            FloorCreate(
                floor_number=0,
                name="Ground",
                organization_id=org.id,
                building_id=building.id,
            ),
        )
    return org, floor


def owner(api_app, *, email: str = "owner@example.com"):
    return seed_org_with_floor(
        api_app,
        email=email,
        user_role=RoleEnum.PG_OWNER,
        member_role=OrganizationRoleEnum.OWNER,
    )


def seed_staff(api_app, org, *, email: str = "staff@example.com") -> None:
    user = api_app.seed(email=email, role=RoleEnum.STAFF)
    with api_app.factory() as session:
        OrganizationMemberRepository(session).create(
            OrganizationMemberCreate(
                organization_id=org.id,
                user_id=user.id,
                role=OrganizationRoleEnum.STAFF,
            ),
        )


def auth(client: TestClient, make_token, *, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def create_payload(
    org, floor, *, room_number: str = "101", room_type: str = "DOUBLE", extra: dict | None = None
) -> dict:
    body = {
        "organization_id": str(org.id),
        "floor_id": str(floor.id),
        "room_number": room_number,
        "room_type": room_type,
    }
    if extra:
        body.update(extra)
    return body


def create_room(
    api_app,
    make_token,
    org,
    floor,
    *,
    email: str = "owner@example.com",
    room_number: str = "101",
    room_type: str = "DOUBLE",
) -> dict:
    headers = auth(api_app.client, make_token, email=email)
    r = api_app.client.post(
        "/api/v1/rooms",
        headers=headers,
        json=create_payload(org, floor, room_number=room_number, room_type=room_type),
    )
    assert r.status_code == 201
    return r.json()


def test_post_rooms_owner_created(api_app, make_token) -> None:
    org, floor = owner(api_app)

    r = api_app.client.post(
        "/api/v1/rooms",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json=create_payload(org, floor),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["floor_id"] == str(floor.id)
    assert body["room_number"] == "101"
    assert body["room_type"] == "DOUBLE"


def test_post_rooms_duplicate_conflict(api_app, make_token) -> None:
    org, floor = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    first = api_app.client.post(
        "/api/v1/rooms",
        headers=headers,
        json=create_payload(org, floor),
    )
    assert first.status_code == 201

    r = api_app.client.post(
        "/api/v1/rooms",
        headers=headers,
        json=create_payload(org, floor),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "room already exists"


def test_post_rooms_staff_forbidden(api_app, make_token) -> None:
    org, floor = seed_org_with_floor(
        api_app,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        member_role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.post(
        "/api/v1/rooms",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json=create_payload(org, floor),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_get_rooms_member_sees_floor(api_app, make_token) -> None:
    org, floor = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    api_app.client.post(
        "/api/v1/rooms",
        headers=headers,
        json=create_payload(org, floor, room_number="201", room_type="SINGLE"),
    )

    r = api_app.client.get(
        "/api/v1/rooms",
        headers=headers,
        params={"organization_id": str(org.id), "floor_id": str(floor.id)},
    )
    assert r.status_code == 200
    assert r.json()[0]["room_number"] == "201"


def test_get_room_member_succeeds(api_app, make_token) -> None:
    org, floor = owner(api_app)
    created = create_room(api_app, make_token, org, floor)

    r = api_app.client.get(
        f"/api/v1/rooms/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_room_missing_not_found(api_app, make_token) -> None:
    owner(api_app)

    r = api_app.client.get(
        f"/api/v1/rooms/{uuid4()}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "room not found"


def test_patch_room_owner_updates_fields(api_app, make_token) -> None:
    org, floor = owner(api_app)
    created = create_room(api_app, make_token, org, floor)

    r = api_app.client.patch(
        f"/api/v1/rooms/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json={"room_number": "  301  ", "room_type": "TRIPLE"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["room_number"] == "301"
    assert body["room_type"] == "TRIPLE"
    assert body["organization_id"] == str(org.id)
    assert body["floor_id"] == str(floor.id)


def test_patch_room_room_type_reflected(api_app, make_token) -> None:
    org, floor = owner(api_app)
    created = create_room(api_app, make_token, org, floor)

    r = api_app.client.patch(
        f"/api/v1/rooms/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json={"room_type": "FOUR_SHARE"},
    )
    assert r.status_code == 200
    assert r.json()["room_type"] == "FOUR_SHARE"


def test_patch_room_staff_forbidden(api_app, make_token) -> None:
    org, floor = owner(api_app)
    seed_staff(api_app, org)
    created = create_room(api_app, make_token, org, floor)

    r = api_app.client.patch(
        f"/api/v1/rooms/{created['id']}",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json={"room_number": "999"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_no_room_response_contains_capacity(api_app, make_token) -> None:
    org, floor = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    created = create_room(api_app, make_token, org, floor)

    responses = [
        api_app.client.post(
            "/api/v1/rooms",
            headers=headers,
            json=create_payload(org, floor, room_number="202"),
        ),
        api_app.client.get(
            "/api/v1/rooms",
            headers=headers,
            params={"organization_id": str(org.id), "floor_id": str(floor.id)},
        ),
        api_app.client.get(f"/api/v1/rooms/{created['id']}", headers=headers),
        api_app.client.patch(
            f"/api/v1/rooms/{created['id']}",
            headers=headers,
            json={"room_number": "203"},
        ),
    ]
    for r in responses:
        assert r.status_code in (200, 201)
        assert "capacity" not in r.json()
        assert "max_beds" not in r.json()
        assert "bed_count" not in r.json()