"""End-to-end tenant stay API tests: auth, org-role authorization, lifecycle."""

from uuid import uuid4

from app.models.enums import (
    BedStatusEnum,
    OrganizationRoleEnum,
    PropertyTypeEnum,
    RoleEnum,
    RoomTypeEnum,
)
from app.repositories.bed import BedRepository
from app.repositories.building import BuildingRepository
from app.repositories.floor import FloorRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.repositories.resident_profile import ResidentProfileRepository
from app.repositories.room import RoomRepository
from app.schemas.bed import BedCreate
from app.schemas.building import BuildingCreate
from app.schemas.floor import FloorCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate
from app.schemas.resident_profile import ResidentProfileCreate
from app.schemas.room import RoomCreate


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
        other_prop = PropertyRepository(session).create(
            PropertyCreate(
                name="Annex PG",
                property_type=PropertyTypeEnum.PG,
                organization_id=org.id,
            ),
        )
        building = BuildingRepository(session).create(
            BuildingCreate(organization_id=org.id, property_id=prop.id, name="Block A"),
        )
        floor = FloorRepository(session).create(
            FloorCreate(
                organization_id=org.id,
                building_id=building.id,
                floor_number=1,
                name="Floor 1",
            ),
        )
        room = RoomRepository(session).create(
            RoomCreate(
                organization_id=org.id,
                floor_id=floor.id,
                room_number="101",
                room_type=RoomTypeEnum.DOUBLE,
            ),
        )
        bed1 = BedRepository(session).create(
            BedCreate(
                organization_id=org.id,
                room_id=room.id,
                bed_number="1",
                status=BedStatusEnum.AVAILABLE,
            ),
        )
        bed2 = BedRepository(session).create(
            BedCreate(
                organization_id=org.id,
                room_id=room.id,
                bed_number="2",
                status=BedStatusEnum.AVAILABLE,
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
    return org, prop, other_prop, bed1, bed2, profile


def owner(api_app, *, email: str = "owner@example.com"):
    return seed_org(
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


def auth(make_token, *, email: str = "owner@example.com") -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def payload(org, profile, prop, bed, **overrides) -> dict:
    body = {
        "organization_id": str(org.id),
        "resident_profile_id": str(profile.id),
        "property_id": str(prop.id),
        "bed_id": str(bed.id),
        "start_date": "2026-01-01",
    }
    body.update(overrides)
    return body


def create_stay(api_app, make_token, org, profile, prop, bed, **overrides) -> dict:
    r = api_app.client.post(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        json=payload(org, profile, prop, bed, **overrides),
    )
    assert r.status_code == 201, r.json()
    return r.json()


def test_post_tenant_stays_owner_created(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)

    r = api_app.client.post(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        json=payload(org, profile, prop, bed),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["resident_profile_id"] == str(profile.id)
    assert body["property_id"] == str(prop.id)
    assert body["bed_id"] == str(bed.id)
    assert body["status"] == "ACTIVE"
    assert body["end_date"] is None


def test_post_tenant_stays_duplicate_active_bed_conflict(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)
    create_stay(api_app, make_token, org, profile, prop, bed)

    r = api_app.client.post(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        json=payload(org, profile, prop, bed, start_date="2026-02-01"),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "bed already has an active stay"


def test_post_tenant_stays_invalid_date_order_conflict(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)

    r = api_app.client.post(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        json=payload(
            org,
            profile,
            prop,
            bed,
            start_date="2026-06-01",
            end_date="2026-01-01",
            status="COMPLETED",
        ),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "end_date must not precede start_date"


def test_post_tenant_stays_property_must_match_bed_conflict(api_app, make_token) -> None:
    org, prop, other_prop, bed, _, profile = owner(api_app)

    r = api_app.client.post(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        json=payload(org, profile, other_prop, bed),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "bed does not belong to the property"


def test_post_tenant_stays_staff_forbidden(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)
    seed_staff(api_app, org)

    r = api_app.client.post(
        "/api/v1/tenant-stays",
        headers=auth(make_token, email="staff@example.com"),
        json=payload(org, profile, prop, bed),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_get_tenant_stays_member_sees_org(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)
    create_stay(api_app, make_token, org, profile, prop, bed)

    r = api_app.client.get(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["bed_id"] == str(bed.id)


def test_get_tenant_stays_resident_filter(api_app, make_token) -> None:
    org, prop, _, bed1, bed2, profile = owner(api_app)
    create_stay(api_app, make_token, org, profile, prop, bed1)
    create_stay(api_app, make_token, org, profile, prop, bed2)

    r = api_app.client.get(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        params={"organization_id": str(org.id), "resident_profile_id": str(profile.id)},
    )
    assert r.status_code == 200
    assert {row["bed_id"] for row in r.json()} == {str(bed1.id), str(bed2.id)}


def test_get_tenant_stays_bed_filter(api_app, make_token) -> None:
    org, prop, _, bed1, bed2, profile = owner(api_app)
    create_stay(api_app, make_token, org, profile, prop, bed1)
    create_stay(api_app, make_token, org, profile, prop, bed2)

    r = api_app.client.get(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        params={"organization_id": str(org.id), "bed_id": str(bed1.id)},
    )
    assert r.status_code == 200
    assert [row["bed_id"] for row in r.json()] == [str(bed1.id)]


def test_get_tenant_stays_status_filter(api_app, make_token) -> None:
    org, prop, _, bed1, bed2, profile = owner(api_app)
    create_stay(api_app, make_token, org, profile, prop, bed1)
    create_stay(
        api_app,
        make_token,
        org,
        profile,
        prop,
        bed2,
        start_date="2024-01-01",
        end_date="2024-06-01",
        status="CANCELLED",
    )

    r = api_app.client.get(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        params={"organization_id": str(org.id), "status": "ACTIVE"},
    )
    assert r.status_code == 200
    assert [row["bed_id"] for row in r.json()] == [str(bed1.id)]

    r = api_app.client.get(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        params={"organization_id": str(org.id), "status": "CANCELLED"},
    )
    assert r.status_code == 200
    assert [row["bed_id"] for row in r.json()] == [str(bed2.id)]


def test_get_tenant_stays_non_member_forbidden(api_app, make_token) -> None:
    org, _, _, _, _, _ = owner(api_app)
    api_app.seed(email="outsider@example.com", role=RoleEnum.TENANT)

    r = api_app.client.get(
        "/api/v1/tenant-stays",
        headers=auth(make_token, email="outsider@example.com"),
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 403


def test_get_tenant_stay_member_succeeds(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)
    created = create_stay(api_app, make_token, org, profile, prop, bed)

    r = api_app.client.get(f"/api/v1/tenant-stays/{created['id']}", headers=auth(make_token))
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_tenant_stay_missing_not_found(api_app, make_token) -> None:
    owner(api_app)

    r = api_app.client.get(f"/api/v1/tenant-stays/{uuid4()}", headers=auth(make_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "tenant stay not found"


def test_patch_tenant_stay_closes_stay(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)
    created = create_stay(api_app, make_token, org, profile, prop, bed)

    r = api_app.client.patch(
        f"/api/v1/tenant-stays/{created['id']}",
        headers=auth(make_token),
        json={"status": "COMPLETED", "end_date": "2026-06-30", "notes": "  Vacated  "},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["end_date"] == "2026-06-30"
    assert body["notes"] == "Vacated"
    # Immutable fields survive the update.
    assert body["bed_id"] == str(bed.id)
    assert body["property_id"] == str(prop.id)
    assert body["resident_profile_id"] == str(profile.id)
    assert body["start_date"] == "2026-01-01"

    # The bed is free again, so a new check-in succeeds.
    r = api_app.client.post(
        "/api/v1/tenant-stays",
        headers=auth(make_token),
        json=payload(org, profile, prop, bed, start_date="2026-07-01"),
    )
    assert r.status_code == 201


def test_patch_tenant_stay_reopen_conflict(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)
    created = create_stay(
        api_app,
        make_token,
        org,
        profile,
        prop,
        bed,
        end_date="2026-06-01",
        status="COMPLETED",
    )

    r = api_app.client.patch(
        f"/api/v1/tenant-stays/{created['id']}",
        headers=auth(make_token),
        json={"status": "ACTIVE"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "a closed stay cannot be reopened"


def test_patch_tenant_stay_rejects_immutable_field(api_app, make_token) -> None:
    org, prop, _, bed, bed2, profile = owner(api_app)
    created = create_stay(api_app, make_token, org, profile, prop, bed)

    r = api_app.client.patch(
        f"/api/v1/tenant-stays/{created['id']}",
        headers=auth(make_token),
        json={"bed_id": str(bed2.id)},
    )
    assert r.status_code == 422


def test_patch_tenant_stay_staff_forbidden(api_app, make_token) -> None:
    org, prop, _, bed, _, profile = owner(api_app)
    seed_staff(api_app, org)
    created = create_stay(api_app, make_token, org, profile, prop, bed)

    r = api_app.client.patch(
        f"/api/v1/tenant-stays/{created['id']}",
        headers=auth(make_token, email="staff@example.com"),
        json={"notes": "nope"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_tenant_stays_missing_token_unauthorized(api_app) -> None:
    r = api_app.client.get(
        "/api/v1/tenant-stays",
        params={"organization_id": str(uuid4())},
    )
    assert r.status_code == 401
