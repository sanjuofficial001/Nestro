"""Pydantic models for the bed API.

`BedUpdate` is deliberately split from the foundation schemas: only the
editable subset of fields exists here. `room_id` and `organization_id` are
immutable — they cannot be sent, so they can never change.

Capacity is intentionally absent: a room's size is the count of its `Bed`
rows (`COUNT(beds.id)`), never persisted or exposed.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BedStatusEnum
from app.schemas.validation import strip_optional


class BedUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bed_number: str | None = Field(default=None, min_length=1, max_length=50)
    status: BedStatusEnum | None = None

    @field_validator("bed_number")
    @classmethod
    def strip_bed_number(cls, value: str | None) -> str | None:
        return strip_optional(value)