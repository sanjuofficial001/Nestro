"""Pydantic models for floors.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`) and string fields are length-bounded and
stripped per SECURITY.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.property import _strip


class FloorBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    building_id: UUID
    floor_number: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip(value)


class FloorCreate(FloorBase):
    """Payload for creating a floor (repository input; no endpoint yet)."""


class FloorRead(FloorBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime