"""Pydantic models for complaints.

Unknown fields are rejected (`extra="forbid"`) and all text is stripped, so an
oversized or padded payload cannot slip past validation (SECURITY.md §3).
`title` and `description` are bounded here rather than in the database: the
columns are `TEXT` and PostgreSQL does not enforce a length on them.

`category` is fixed at creation — a complaint is filed under the category it was
raised as, so `category` does not appear in `ComplaintUpdate`
(`app/schemas/complaint_api.py`) and a PATCH that carries it fails validation.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    ComplaintCategoryEnum,
    ComplaintPriorityEnum,
    ComplaintStatusEnum,
)
from app.schemas.property import _strip

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 2000


def _strip_text(value: str | None) -> str | None:
    """Strip surrounding whitespace and reject an all-whitespace payload.

    `min_length` is checked by Pydantic before this validator runs, so `"   "`
    would otherwise satisfy it and then store an empty string.
    """
    if value is None:
        return None
    stripped = _strip(value)
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class ComplaintBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    property_id: UUID
    resident_profile_id: UUID
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH)
    category: ComplaintCategoryEnum
    priority: ComplaintPriorityEnum = ComplaintPriorityEnum.MEDIUM
    status: ComplaintStatusEnum = ComplaintStatusEnum.OPEN
    assigned_to_member_id: UUID | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return _strip_text(value)


class ComplaintCreate(ComplaintBase):
    """Payload for creating a complaint."""


class ComplaintRead(ComplaintBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
