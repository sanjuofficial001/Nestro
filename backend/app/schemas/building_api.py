"""Pydantic models for the building API.

`BuildingUpdate` is deliberately split from the foundation schemas: only the
editable subset of fields exists here. `organization_id` and `property_id`
are immutable — they cannot be sent, so they can never change.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validation import strip_optional


class BuildingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return strip_optional(value)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return strip_optional(value)