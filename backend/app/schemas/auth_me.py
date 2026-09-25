"""Pydantic response model for the authenticated current-user endpoint.

The shape mirrors the `users` row exactly: JWT claims are never surfaced and
`is_verified`/relationships stay internal. Following SECURITY.md, unknown
fields are rejected (`extra="forbid"`).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import RoleEnum


class AuthMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    email: EmailStr
    phone: str
    full_name: str
    role: RoleEnum
    is_active: bool
    created_at: datetime
    updated_at: datetime