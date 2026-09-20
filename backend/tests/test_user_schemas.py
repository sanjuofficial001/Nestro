"""Tests for user schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import RoleEnum
from app.models.user import User
from app.schemas.user import UserCreate, UserRead


def test_user_create_valid() -> None:
    data = UserCreate(
        email="resident@example.com",
        full_name=" Ravi Kumar ",
        role=RoleEnum.TENANT,
    )
    assert data.email == "resident@example.com"
    assert data.full_name == "Ravi Kumar"
    assert data.phone is None
    assert data.role is RoleEnum.TENANT


def test_user_create_with_phone() -> None:
    data = UserCreate(
        email="owner@example.com",
        phone="+919000000000",
        full_name="Owner",
        role=RoleEnum.PG_OWNER,
    )
    assert data.phone == "+919000000000"


def test_user_create_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", full_name="x", role=RoleEnum.STAFF)


def test_user_create_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="a@example.com",
            full_name="x",
            role=RoleEnum.STAFF,
            token="extra",
        )


def test_user_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="a@example.com", full_name="", role=RoleEnum.STAFF)


def test_user_create_rejects_unknown_role() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="a@example.com", full_name="x", role="BOSS")


def test_user_read_from_attributes() -> None:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email="resident@example.com",
        phone=None,
        full_name="Ravi Kumar",
        role=RoleEnum.TENANT,
        is_active=True,
        is_verified=False,
        created_at=now,
        updated_at=now,
    )
    read = UserRead.model_validate(user)
    assert read.id == user.id
    assert read.email == "resident@example.com"
    assert read.role is RoleEnum.TENANT
    assert read.is_active is True
    assert read.created_at == now