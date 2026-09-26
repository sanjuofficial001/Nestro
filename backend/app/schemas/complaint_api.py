"""Pydantic models for the complaint API.

`ComplaintUpdate` is deliberately split from the foundation schemas: only the
editable subset of fields exists here. `organization_id`, `property_id`,
`resident_profile_id`, and `category` are immutable — they cannot be sent, so
they can never change.

Two things are intentionally absent from this file:

- `category`, because a complaint is filed under the category it was raised as;
- `resolved_at`, because stamping it belongs to the workflow milestone
  (DATABASE.md §19), not to this CRUD surface.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ComplaintPriorityEnum, ComplaintStatusEnum
from app.schemas.complaint import (
    DESCRIPTION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    _strip_text,
)


class ComplaintUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str | None = Field(
        default=None, min_length=1, max_length=DESCRIPTION_MAX_LENGTH
    )
    status: ComplaintStatusEnum | None = None
    priority: ComplaintPriorityEnum | None = None
    assigned_to_member_id: UUID | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _strip_text(value)
