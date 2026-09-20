"""Pydantic models for buildings.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`) and string fields are length-bounded and
stripped per SECURITY.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.property import _strip, _strip_optional


class BuildingBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    property_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip(value)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class BuildingCreate(BuildingBase):
    """Payload for creating a building (repository input; no endpoint yet)."""


class BuildingRead(BuildingBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime