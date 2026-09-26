"""Pydantic models for resident profiles.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`) and string fields are length-bounded and
stripped per SECURITY.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validation import strip_optional, strip_text


class ResidentProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    organization_member_id: UUID
    property_id: UUID | None = None
    emergency_contact_name: str = Field(min_length=1, max_length=255)
    emergency_contact_phone: str = Field(min_length=1, max_length=20)
    address: str = Field(min_length=1, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool = True

    @field_validator("emergency_contact_name", "emergency_contact_phone")
    @classmethod
    def strip_short_fields(cls, value: str) -> str:
        return strip_text(value)

    @field_validator("address")
    @classmethod
    def strip_address(cls, value: str) -> str:
        return strip_text(value)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return strip_optional(value)


class ResidentProfileCreate(ResidentProfileBase):
    """Payload for creating a resident profile (repository input; no endpoint yet)."""


class ResidentProfileRead(ResidentProfileBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime