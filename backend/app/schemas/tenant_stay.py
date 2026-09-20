"""Pydantic models for tenant stays.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`); `end_date` and `notes` are optional — an open
(`ACTIVE`) stay has no `end_date` yet. The active-stay-per-bed guarantee is a
database-level partial unique index, not a schema rule.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TenantStayStatusEnum
from app.schemas.property import _strip_optional


class TenantStayBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    resident_profile_id: UUID
    property_id: UUID
    bed_id: UUID
    start_date: date
    end_date: date | None = None
    status: TenantStayStatusEnum = TenantStayStatusEnum.ACTIVE
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class TenantStayCreate(TenantStayBase):
    """Payload for creating a tenant stay (repository input; no endpoint yet)."""


class TenantStayRead(TenantStayBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime