"""Pydantic models for rooms.

Only create/read shapes exist: no endpoints rely on these yet. Unknown fields
are rejected (`extra="forbid"`) and string fields are length-bounded and
stripped per SECURITY.md.

Capacity is intentionally absent: it is derived from the room's `Bed` rows
(`COUNT(beds.id)`), never persisted.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RoomTypeEnum
from app.schemas.property import _strip


class RoomBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    floor_id: UUID
    room_number: str = Field(min_length=1, max_length=50)
    room_type: RoomTypeEnum

    @field_validator("room_number")
    @classmethod
    def strip_room_number(cls, value: str) -> str:
        return _strip(value)


class RoomCreate(RoomBase):
    """Payload for creating a room (repository input; no endpoint yet)."""


class RoomRead(RoomBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    created_at: datetime
    updated_at: datetime