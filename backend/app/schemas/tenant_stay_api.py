"""Pydantic models for the tenant stay API.

`TenantStayUpdate` is deliberately split from the foundation schemas: only the
editable subset of fields exists here. `organization_id`, `resident_profile_id`,
`property_id`, `bed_id`, and `start_date` are immutable — they cannot be sent,
so they can never change (a stay records who/where/when it began; transfers and
resident reassignment are not part of this surface).

Occupancy is not stored here: a bed is occupied when an `ACTIVE` stay exists,
never through a bed field.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TenantStayStatusEnum
from app.schemas.property import _strip_optional


class TenantStayUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    end_date: date | None = None
    status: TenantStayStatusEnum | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return _strip_optional(value)
