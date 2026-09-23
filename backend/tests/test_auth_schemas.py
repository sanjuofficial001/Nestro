"""Tests for the registration request/response schema validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import RoleEnum
from app.models.user import User
from app.schemas.auth import RegisterRequest, RegisterResponse

REGISTER_PAYLOAD = {
    "email": "USER@Example.com",
    "phone": " 9876543210 ",
    "full_name": " John Doe ",
    "password": "StrongPass123",
}


def test_register_request_valid() -> None:
    data = RegisterRequest.model_validate(REGISTER_PAYLOAD)
    assert data.email == "user@example.com"
    assert data.phone == "9876543210"
    assert data.full_name == "John Doe"
    assert data.password == "StrongPass123"


def test_register_request_rejects_invalid_email() -> None:
    payload = {**REGISTER_PAYLOAD, "email": "not-an-email"}
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(payload)


def test_register_request_rejects_short_password() -> None:
    payload = {**REGISTER_PAYLOAD, "password": "Short1"}
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(payload)


def test_register_request_rejects_extra_field() -> None:
    payload = {**REGISTER_PAYLOAD, "token": "extra"}
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(payload)


def test_register_request_normalizes_email_case() -> None:
    data = RegisterRequest.model_validate(REGISTER_PAYLOAD)
    assert data.email == "user@example.com"


def test_register_request_strips_string_fields() -> None:
    data = RegisterRequest.model_validate(REGISTER_PAYLOAD)
    assert data.phone == "9876543210"
    assert data.full_name == "John Doe"


def test_register_response_from_attributes() -> None:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email="user@example.com",
        phone="9876543210",
        full_name="John Doe",
        role=RoleEnum.TENANT,
        is_active=True,
        is_verified=False,
        created_at=now,
        updated_at=now,
    )
    response = RegisterResponse.model_validate(user)
    assert response.id == user.id
    assert response.email == "user@example.com"
    assert response.phone == "9876543210"
    assert response.full_name == "John Doe"
    assert response.created_at == now