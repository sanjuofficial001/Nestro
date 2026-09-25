"""Pydantic models for organization onboarding.

The request creates the user's first organization and owner membership. Slugs are
validated exactly like `OrganizationBase` (lowercase, whitespace-free); unknown
fields are rejected (`extra="forbid"`) per SECURITY.md.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import OrganizationRoleEnum


def _strip(value: str) -> str:
    return value.strip()


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_name: str = Field(min_length=1, max_length=255)
    organization_slug: str = Field(min_length=3, max_length=100)

    @field_validator("organization_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip(value)

    @field_validator("organization_slug")
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


class OnboardingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    organization_id: UUID
    organization_name: str
    organization_slug: str
    membership_id: UUID
    role: OrganizationRoleEnum