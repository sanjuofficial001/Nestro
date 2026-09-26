"""Pydantic models for the registration milestone.

Only the register request/response shapes exist: no login or token concerns yet.
Following SECURITY.md, unknown fields are rejected (`extra="forbid"`), the email
is normalized to lowercase, and string fields are stripped.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.validation import strip_text


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    phone: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower().strip()

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str) -> str:
        return strip_text(value)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        return strip_text(value)


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    email: EmailStr
    phone: str
    full_name: str
    created_at: datetime