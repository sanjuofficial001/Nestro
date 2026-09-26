"""End-to-end bed API tests: auth, org-role authorization, no capacity keys."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.enums import (
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
    RoomTypeEnum,
)
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.room import RoomRepository
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.room import RoomCreate


def seed_org_with_room(
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
        room = RoomRepository(session).create(
            RoomCreate(
                room_number="101",
                room_type=RoomTypeEnum.DOUBLE,
                organization_id=org.id,
                floor_id=floor.id,
            ),
        )
    return org, room


def owner(api_app, *, email: str = "owner@example.com"):
    return seed_org_with_room(
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
    org, room, *, bed_number: str = "1", status: str = "AVAILABLE", extra: dict | None = None
) -> dict:
    body = {
        "organization_id": str(org.id),
        "room_id": str(room.id),
        "bed_number": bed_number,
        "status": status,
    }
    if extra:
        body.update(extra)
    return body


def create_bed(
    api_app,
    make_token,
    org,
    room,
    *,
    email: str = "owner@example.com",
    bed_number: str = "1",
) -> dict:
    headers = auth(api_app.client, make_token, email=email)
    r = api_app.client.post(
        "/api/v1/beds",
        headers=headers,
        json=create_payload(org, room, bed_number=bed_number),
    )
    assert r.status_code == 201
    return r.json()


def test_post_beds_owner_created(api_app, make_token) -> None:
    org, room = owner(api_app)

    r = api_app.client.post(
        "/api/v1/beds",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json=create_payload(org, room),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["room_id"] == str(room.id)
    assert body["bed_number"] == "1"
    assert body["status"] == "AVAILABLE"


def test_post_beds_duplicate_conflict(api_app, make_token) -> None:
    org, room = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    first = api_app.client.post(
        "/api/v1/beds",
        headers=headers,
        json=create_payload(org, room),
    )
    assert first.status_code == 201

    r = api_app.client.post(
        "/api/v1/beds",
        headers=headers,
        json=create_payload(org, room),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "bed already exists"


def test_post_beds_staff_forbidden(api_app, make_token) -> None:
    org, room = seed_org_with_room(
        api_app,
        email="staff@example.com",
        user_role=RoleEnum.STAFF,
        member_role=OrganizationRoleEnum.STAFF,
    )

    r = api_app.client.post(
        "/api/v1/beds",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json=create_payload(org, room),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_get_beds_member_sees_room(api_app, make_token) -> None:
    org, room = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    api_app.client.post(
        "/api/v1/beds",
        headers=headers,
        json=create_payload(org, room, bed_number="A1"),
    )

    r = api_app.client.get(
        "/api/v1/beds",
        headers=headers,
        params={"organization_id": str(org.id), "room_id": str(room.id)},
    )
    assert r.status_code == 200
    assert r.json()[0]["bed_number"] == "A1"


def test_get_bed_member_succeeds(api_app, make_token) -> None:
    org, room = owner(api_app)
    created = create_bed(api_app, make_token, org, room)

    r = api_app.client.get(
        f"/api/v1/beds/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_bed_missing_not_found(api_app, make_token) -> None:
    owner(api_app)

    r = api_app.client.get(
        f"/api/v1/beds/{uuid4()}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "bed not found"


def test_patch_bed_owner_updates_fields(api_app, make_token) -> None:
    org, room = owner(api_app)
    created = create_bed(api_app, make_token, org, room)

    r = api_app.client.patch(
        f"/api/v1/beds/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json={"bed_number": "  B2  ", "status": "MAINTENANCE"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["bed_number"] == "B2"
    assert body["status"] == "MAINTENANCE"
    assert body["organization_id"] == str(org.id)
    assert body["room_id"] == str(room.id)


def test_patch_bed_staff_forbidden(api_app, make_token) -> None:
    org, room = owner(api_app)
    seed_staff(api_app, org)
    created = create_bed(api_app, make_token, org, room)

    r = api_app.client.patch(
        f"/api/v1/beds/{created['id']}",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json={"bed_number": "999"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_no_bed_response_contains_capacity(api_app, make_token) -> None:
    org, room = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    created = create_bed(api_app, make_token, org, room)

    responses = [
        api_app.client.post(
            "/api/v1/beds",
            headers=headers,
            json=create_payload(org, room, bed_number="2"),
        ),
        api_app.client.get(
            "/api/v1/beds",
            headers=headers,
            params={"organization_id": str(org.id), "room_id": str(room.id)},
        ),
        api_app.client.get(f"/api/v1/beds/{created['id']}", headers=headers),
        api_app.client.patch(
            f"/api/v1/beds/{created['id']}",
            headers=headers,
            json={"bed_number": "3"},
        ),
    ]
    for r in responses:
        assert r.status_code in (200, 201)
        assert "capacity" not in r.json()
        assert "max_beds" not in r.json()
        assert "bed_count" not in r.json()