"""Current-user and authorization tests — the FastAPI dependency seam.

`auth_app` wires the real `get_current_user` / `require_role` / `require_any_role`
guards to an in-memory database. Identity resolves from the verified token email
(case-insensitive); role and `is_active` come from the database row, never from
JWT claims.
"""

import datetime as _dt

from app.models.enums import RoleEnum


def test_valid_token_resolves_existing_user(auth_app, make_token) -> None:
    auth_app.seed(email="user@example.com", role=RoleEnum.TENANT)
    response = auth_app.client.get(
        "/me",
        headers={"Authorization": f"Bearer {make_token(email='user@example.com')}"},
    )
    assert response.status_code == 200
    assert response.json() == {"email": "user@example.com"}


def test_valid_token_with_unknown_user_rejected(auth_app, make_token) -> None:
    response = auth_app.client.get(
        "/me",
        headers={"Authorization": f"Bearer {make_token(email='nobody@example.com')}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication failed"}


def test_valid_token_with_inactive_user_rejected(auth_app, make_token) -> None:
    auth_app.seed(email="ghost@example.com", role=RoleEnum.TENANT, is_active=False)
    response = auth_app.client.get(
        "/me",
        headers={"Authorization": f"Bearer {make_token(email='ghost@example.com')}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication failed"}


def test_email_mapping_is_case_insensitive(auth_app, make_token) -> None:
    auth_app.seed(email="user@example.com", role=RoleEnum.TENANT)
    response = auth_app.client.get(
        "/me",
        headers={"Authorization": f"Bearer {make_token(email='User@Example.COM')}"},
    )
    assert response.status_code == 200
    assert response.json() == {"email": "user@example.com"}


def test_role_comes_from_database_not_token(auth_app, make_token) -> None:
    auth_app.seed(email="user@example.com", role=RoleEnum.TENANT)
    token = make_token(email="user@example.com", role=RoleEnum.PG_OWNER)
    me = auth_app.client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"email": "user@example.com"}
    owner_ops = auth_app.client.get("/owner-ops", headers={"Authorization": f"Bearer {token}"})
    assert owner_ops.status_code == 403
    assert owner_ops.json() == {"detail": "Forbidden"}


def test_allowed_role_succeeds(auth_app, make_token) -> None:
    auth_app.seed(email="owner@example.com", role=RoleEnum.PG_OWNER)
    response = auth_app.client.get(
        "/owner-ops",
        headers={"Authorization": f"Bearer {make_token(email='owner@example.com')}"},
    )
    assert response.status_code == 200
    assert response.json() == {"email": "owner@example.com", "role": "PG_OWNER"}


def test_disallowed_role_fails(auth_app, make_token) -> None:
    auth_app.seed(email="staff@example.com", role=RoleEnum.STAFF)
    response = auth_app.client.get(
        "/owner-ops",
        headers={"Authorization": f"Bearer {make_token(email='staff@example.com')}"},
    )
    assert response.status_code == 403


def test_super_admin_passes_every_guard(auth_app, make_token) -> None:
    auth_app.seed(email="root@example.com", role=RoleEnum.SUPER_ADMIN)
    token = make_token(email="root@example.com")
    admin = auth_app.client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert admin.status_code == 200
    assert admin.json()["role"] == "SUPER_ADMIN"
    owner_ops = auth_app.client.get("/owner-ops", headers={"Authorization": f"Bearer {token}"})
    assert owner_ops.status_code == 200


def test_missing_bearer_token_rejected(auth_app) -> None:
    response = auth_app.client.get("/me")
    assert response.status_code == 401


def test_expired_token_rejected(auth_app, make_token) -> None:
    auth_app.seed(email="user@example.com", role=RoleEnum.TENANT)
    token = make_token(email="user@example.com", expires_in=-_dt.timedelta(hours=1))
    response = auth_app.client.get(
        "/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_malformed_token_rejected(auth_app) -> None:
    response = auth_app.client.get(
        "/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401