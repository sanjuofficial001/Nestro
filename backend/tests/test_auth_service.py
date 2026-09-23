"""Tests for the registration service flow."""

import pytest

from app.models.enums import RoleEnum
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService


def register(db_session, *, email: str = "user@example.com") -> None:
    AuthService(db_session).register_user(
        RegisterRequest(
            email=email,
            phone="9876543210",
            full_name="John Doe",
            password="StrongPass123",
        )
    )


def test_register_user_creates_tenant(db_session) -> None:
    user = AuthService(db_session).register_user(
        RegisterRequest(
            email="USER@Example.com",
            phone="9876543210",
            full_name="John Doe",
            password="StrongPass123",
        )
    )
    assert user.id is not None
    assert user.email == "user@example.com"
    assert user.phone == "9876543210"
    assert user.full_name == "John Doe"
    assert user.role is RoleEnum.TENANT
    assert user.created_at is not None


def test_register_user_duplicate_email_raises(db_session) -> None:
    register(db_session)
    with pytest.raises(ValueError, match="email already exists"):
        AuthService(db_session).register_user(
            RegisterRequest(
                email="USER@example.com",
                phone="9999999999",
                full_name="Jane Doe",
                password="AnotherPass123",
            )
        )


def test_register_user_stores_no_password(db_session) -> None:
    AuthService(db_session).register_user(
        RegisterRequest(
            email="user@example.com",
            phone="9876543210",
            full_name="John Doe",
            password="StrongPass123",
        )
    )
    columns = set(User.__table__.columns.keys())
    assert "password" not in columns
    assert "password_hash" not in columns


def test_register_user_returns_created_user(db_session) -> None:
    AuthService(db_session).register_user(
        RegisterRequest(
            email="user@example.com",
            phone="9876543210",
            full_name="John Doe",
            password="StrongPass123",
        )
    )
    fetched = UserRepository(db_session).get_by_email("USER@example.com")
    assert fetched is not None
    assert fetched.email == "user@example.com"
    assert fetched.role is RoleEnum.TENANT