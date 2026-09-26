"""Pydantic models for beds.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`) and string fields are length-bounded and
stripped per SECURITY.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BedStatusEnum
from app.schemas.validation import strip_text


class BedBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    room_id: UUID
    bed_number: str = Field(min_length=1, max_length=50)
    status: BedStatusEnum = BedStatusEnum.AVAILABLE

    @field_validator("bed_number")
    @classmethod
    def strip_bed_number(cls, value: str) -> str:
        return strip_text(value)


class BedCreate(BedBase):
    """Payload for creating a bed (repository input; no endpoint yet)."""


class BedRead(BedBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime