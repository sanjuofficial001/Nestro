"""End-to-end resident profile API tests: auth, org-role authorization, ids."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.enums import OrganizationRoleEnum, PropertyTypeEnum, RoleEnum
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_member import OrganizationMemberRepository
from app.repositories.property import PropertyRepository
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate
from app.schemas.property import PropertyCreate


def seed_org(
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
    return org, member, prop


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


def auth(client: TestClient, make_token, *, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def create_payload(org, member, prop, *, emergency_contact_name: str = "Asha Rao") -> dict:
    return {
        "organization_id": str(org.id),
        "organization_member_id": str(member.id),
        "property_id": str(prop.id),
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_phone": "9876543210",
        "address": "12 MG Road",
    }


def create_profile(
    api_app, make_token, org, member, prop, *, email: str = "owner@example.com"
) -> dict:
    headers = auth(api_app.client, make_token, email=email)
    r = api_app.client.post(
        "/api/v1/resident-profiles",
        headers=headers,
        json=create_payload(org, member, prop),
    )
    assert r.status_code == 201
    return r.json()


def test_post_resident_profiles_owner_created(api_app, make_token) -> None:
    org, member, prop = owner(api_app)

    r = api_app.client.post(
        "/api/v1/resident-profiles",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json=create_payload(org, member, prop),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["organization_member_id"] == str(member.id)
    assert body["property_id"] == str(prop.id)
    assert body["is_active"] is True


def test_post_resident_profiles_duplicate_conflict(api_app, make_token) -> None:
    org, member, prop = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    first = api_app.client.post(
        "/api/v1/resident-profiles",
        headers=headers,
        json=create_payload(org, member, prop),
    )
    assert first.status_code == 201

    r = api_app.client.post(
        "/api/v1/resident-profiles",
        headers=headers,
        json=create_payload(org, member, prop),
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "resident profile already exists"


def test_post_resident_profiles_staff_forbidden(api_app, make_token) -> None:
    org, member, prop = owner(api_app)
    seed_staff(api_app, org)

    r = api_app.client.post(
        "/api/v1/resident-profiles",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json=create_payload(org, member, prop),
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_get_resident_profiles_member_sees_org(api_app, make_token) -> None:
    org, member, prop = owner(api_app)
    headers = auth(api_app.client, make_token, email="owner@example.com")
    api_app.client.post(
        "/api/v1/resident-profiles",
        headers=headers,
        json=create_payload(org, member, prop),
    )

    r = api_app.client.get(
        "/api/v1/resident-profiles",
        headers=headers,
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["emergency_contact_name"] == "Asha Rao"


def test_get_resident_profiles_non_member_forbidden(api_app, make_token) -> None:
    org, _, _ = owner(api_app)
    api_app.seed(email="outsider@example.com", role=RoleEnum.TENANT)

    r = api_app.client.get(
        "/api/v1/resident-profiles",
        headers=auth(api_app.client, make_token, email="outsider@example.com"),
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 403


def test_get_resident_profile_member_succeeds(api_app, make_token) -> None:
    org, member, prop = owner(api_app)
    created = create_profile(api_app, make_token, org, member, prop)

    r = api_app.client.get(
        f"/api/v1/resident-profiles/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_resident_profile_missing_not_found(api_app, make_token) -> None:
    owner(api_app)

    r = api_app.client.get(
        f"/api/v1/resident-profiles/{uuid4()}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "resident profile not found"


def test_patch_resident_profile_owner_updates_fields(api_app, make_token) -> None:
    org, member, prop = owner(api_app)
    created = create_profile(api_app, make_token, org, member, prop)

    r = api_app.client.patch(
        f"/api/v1/resident-profiles/{created['id']}",
        headers=auth(api_app.client, make_token, email="owner@example.com"),
        json={"emergency_contact_name": "  Asha Menon  ", "is_active": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["emergency_contact_name"] == "Asha Menon"
    assert body["is_active"] is False
    assert body["organization_id"] == str(org.id)
    assert body["organization_member_id"] == str(member.id)


def test_patch_resident_profile_staff_forbidden(api_app, make_token) -> None:
    org, member, prop = owner(api_app)
    seed_staff(api_app, org)
    created = create_profile(api_app, make_token, org, member, prop)

    r = api_app.client.patch(
        f"/api/v1/resident-profiles/{created['id']}",
        headers=auth(api_app.client, make_token, email="staff@example.com"),
        json={"is_active": False},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient permissions"


def test_resident_profiles_missing_token_unauthorized(api_app) -> None:
    r = api_app.client.get(
        "/api/v1/resident-profiles",
        params={"organization_id": str(uuid4())},
    )
    assert r.status_code == 401


def test_resident_profiles_invalid_token_unauthorized(api_app, make_token) -> None:
    r = api_app.client.get(
        "/api/v1/resident-profiles",
        headers={"Authorization": "Bearer not-a-valid-token"},
        params={"organization_id": str(uuid4())},
    )
    assert r.status_code == 401


def test_resident_profiles_inactive_user_unauthorized(api_app, make_token) -> None:
    org, _, _ = owner(api_app)
    api_app.seed(email="suspended@example.com", role=RoleEnum.PG_OWNER, is_active=False)

    r = api_app.client.get(
        "/api/v1/resident-profiles",
        headers=auth(api_app.client, make_token, email="suspended@example.com"),
        params={"organization_id": str(org.id)},
    )
    assert r.status_code == 401
