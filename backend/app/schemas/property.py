"""Pydantic models for properties.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`) and string fields are length-bounded and
stripped per SECURITY.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import PropertyStatusEnum, PropertyTypeEnum
from app.schemas.validation import strip_optional, strip_text


class PropertyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    name: str = Field(min_length=1, max_length=255)
    property_type: PropertyTypeEnum
    address: str | None = Field(default=None, max_length=1000)
    contact_phone: str | None = Field(default=None, max_length=20)
    rules: str | None = Field(default=None, max_length=4000)
    status: PropertyStatusEnum = PropertyStatusEnum.ACTIVE

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return strip_text(value)

    @field_validator("address", "rules")
    @classmethod
    def strip_long_text(cls, value: str | None) -> str | None:
        return strip_optional(value)


class PropertyCreate(PropertyBase):
    """Payload for creating a property (repository input; no endpoint yet)."""


class PropertyRead(PropertyBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None