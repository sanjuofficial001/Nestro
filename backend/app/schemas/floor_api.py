"""Pydantic models for the floor API.

`FloorUpdate` is deliberately split from the foundation schemas: only the
editable subset of fields exists here. `building_id` and `organization_id`
are immutable — they cannot be sent, so they can never change.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validation import strip_optional


class FloorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    floor_number: int | None = Field(default=None, ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return strip_optional(value)