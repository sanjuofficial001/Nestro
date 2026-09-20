"""Pydantic models for users.

Only create/read shapes exist: no authentication endpoints rely on these yet.
Following SECURITY.md, unknown fields are rejected (`extra="forbid"`) and string
fields are length-bounded.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import RoleEnum


def _strip(value: str) -> str:
    return value.strip()


class UserBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    role: RoleEnum

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        return _strip(value)


class UserCreate(UserBase):
    """Payload for creating a user (repository input; no endpoint yet)."""


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime