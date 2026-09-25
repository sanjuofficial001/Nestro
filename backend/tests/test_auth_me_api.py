"""Tests for the authenticated current-user endpoint (GET /api/v1/auth/me).

`api_app` mounts the real v1 router against the in-memory database, so these
exercise the actual endpoint, dependency, and schema path. Role and `is_active`
always come from the database row; the JWT only proves identity.
"""

import datetime as _dt

from app.models.enums import RoleEnum

PHONE = "+919000000000"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_me_returns_current_user_profile(api_app, make_token) -> None:
    user = api_app.seed(email="user@example.com", role=RoleEnum.TENANT, phone=PHONE)
    response = api_app.client.get(
        "/api/v1/auth/me",
        headers=_auth(make_token(email="user@example.com")),
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": "user@example.com",
        "phone": PHONE,
        "full_name": "Test User",
        "role": "TENANT",
        "is_active": True,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def test_auth_me_any_role_can_access(api_app, make_token) -> None:
    for index, role in enumerate(RoleEnum):
        email = f"{role.value.lower()}@example.com"
        api_app.seed(email=email, role=role, phone=f"+9190000000{index}")
        response = api_app.client.get(
            "/api/v1/auth/me",
            headers=_auth(make_token(email=email)),
        )
        assert response.status_code == 200
        assert response.json()["role"] == role.value


def test_auth_me_role_comes_from_database(api_app, make_token) -> None:
    api_app.seed(email="user@example.com", role=RoleEnum.TENANT, phone=PHONE)
    token = make_token(email="user@example.com", role=RoleEnum.PG_OWNER)
    response = api_app.client.get("/api/v1/auth/me", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["role"] == "TENANT"


def test_auth_me_missing_token_rejected(api_app) -> None:
    response = api_app.client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication failed"}


def test_auth_me_expired_token_rejected(api_app, make_token) -> None:
    api_app.seed(email="user@example.com", role=RoleEnum.TENANT, phone=PHONE)
    token = make_token(email="user@example.com", expires_in=-_dt.timedelta(hours=1))
    response = api_app.client.get("/api/v1/auth/me", headers=_auth(token))
    assert response.status_code == 401


def test_auth_me_unknown_user_rejected(api_app, make_token) -> None:
    response = api_app.client.get(
        "/api/v1/auth/me",
        headers=_auth(make_token(email="nobody@example.com")),
    )
    assert response.status_code == 401


def test_auth_me_inactive_user_rejected(api_app, make_token) -> None:
    api_app.seed(
        email="ghost@example.com",
        role=RoleEnum.TENANT,
        is_active=False,
        phone=PHONE,
    )
    response = api_app.client.get(
        "/api/v1/auth/me",
        headers=_auth(make_token(email="ghost@example.com")),
    )
    assert response.status_code == 401