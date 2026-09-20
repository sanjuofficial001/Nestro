"""Pydantic models for organizations.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`) per SECURITY.md; slugs are lowercase and free of
whitespace.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip(value: str) -> str:
    return value.strip()


class OrganizationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=3, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip(value)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        stripped = _strip(value)
        if stripped != value:
            raise ValueError("slug must not have leading or trailing whitespace")
        if value != value.lower():
            raise ValueError("slug must be lowercase")
        if any(char.isspace() for char in value):
            raise ValueError("slug must not contain spaces")
        return stripped


class OrganizationCreate(OrganizationBase):
    """Payload for creating an organization (repository input; no endpoint yet)."""


class OrganizationRead(OrganizationBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime