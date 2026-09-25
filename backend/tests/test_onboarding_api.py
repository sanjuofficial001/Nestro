"""Tests for the onboarding endpoint (POST /api/v1/auth/onboard).

`api_app` mounts the real v1 router against the in-memory database, so these
exercise the actual endpoint, dependency, and schema path.
"""

from app.models.enums import RoleEnum

ONBOARD_PAYLOAD = {"organization_name": "My PG", "organization_slug": "my-pg"}


def _auth(email: str, make_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(email=email)}"}


def test_onboard_creates_organization_and_owner_membership(api_app, make_token) -> None:
    api_app.seed(email="owner@example.com", role=RoleEnum.PG_OWNER, phone="+919000000001")
    response = api_app.client.post(
        "/api/v1/auth/onboard",
        headers=_auth("owner@example.com", make_token),
        json=ONBOARD_PAYLOAD,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["organization_name"] == "My PG"
    assert body["organization_slug"] == "my-pg"
    assert body["organization_id"]
    assert body["membership_id"]
    assert body["role"] == "OWNER"


def test_onboard_duplicate_slug_conflict(api_app, make_token) -> None:
    api_app.seed(email="owner@example.com", role=RoleEnum.PG_OWNER, phone="+919000000001")
    api_app.seed(email="other@example.com", role=RoleEnum.PG_OWNER, phone="+919000000002")
    api_app.client.post(
        "/api/v1/auth/onboard",
        headers=_auth("owner@example.com", make_token),
        json=ONBOARD_PAYLOAD,
    )
    response = api_app.client.post(
        "/api/v1/auth/onboard",
        headers=_auth("other@example.com", make_token),
        json=ONBOARD_PAYLOAD,
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "organization slug already exists"}


def test_onboard_already_onboarded_conflict(api_app, make_token) -> None:
    api_app.seed(email="owner@example.com", role=RoleEnum.PG_OWNER, phone="+919000000001")
    api_app.client.post(
        "/api/v1/auth/onboard",
        headers=_auth("owner@example.com", make_token),
        json=ONBOARD_PAYLOAD,
    )
    response = api_app.client.post(
        "/api/v1/auth/onboard",
        headers=_auth("owner@example.com", make_token),
        json={"organization_name": "Other PG", "organization_slug": "other-pg"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "user already onboarded"}


def test_onboard_missing_token_rejected(api_app) -> None:
    response = api_app.client.post("/api/v1/auth/onboard", json=ONBOARD_PAYLOAD)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication failed"}


def test_onboard_inactive_user_rejected(api_app, make_token) -> None:
    api_app.seed(
        email="ghost@example.com",
        role=RoleEnum.PG_OWNER,
        is_active=False,
        phone="+919000000001",
    )
    response = api_app.client.post(
        "/api/v1/auth/onboard",
        headers=_auth("ghost@example.com", make_token),
        json=ONBOARD_PAYLOAD,
    )
    assert response.status_code == 401