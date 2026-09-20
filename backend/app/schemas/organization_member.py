"""Pydantic models for organization memberships.

Unknown fields are rejected (`extra="forbid"`) per SECURITY.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import OrganizationRoleEnum


class OrganizationMemberBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    user_id: UUID
    role: OrganizationRoleEnum


class OrganizationMemberCreate(OrganizationMemberBase):
    """Payload for creating a membership (repository input; no endpoint yet)."""


class OrganizationMemberRead(OrganizationMemberBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime