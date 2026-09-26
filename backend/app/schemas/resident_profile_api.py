"""Pydantic models for the resident profile API.

`ResidentProfileUpdate` is deliberately split from the foundation schemas: only
the editable subset of fields exists here. `organization_id` and
`organization_member_id` are immutable — they cannot be sent, so they can never
change, and `UNIQUE (organization_member_id)` is therefore unreachable from an
update. `property_id` stays optional; omitted or null fields are left unchanged.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.property import _strip, _strip_optional


class ResidentProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: UUID | None = None
    emergency_contact_name: str | None = Field(default=None, min_length=1, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, min_length=1, max_length=20)
    address: str | None = Field(default=None, min_length=1, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None

    @field_validator("emergency_contact_name", "emergency_contact_phone", "address")
    @classmethod
    def strip_fields(cls, value: str | None) -> str | None:
        return _strip(value) if value else value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return _strip_optional(value)