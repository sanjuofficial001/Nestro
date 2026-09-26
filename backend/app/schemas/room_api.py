"""Pydantic models for the room API.

`RoomUpdate` is deliberately split from the foundation schemas: only the
editable subset of fields exists here. `floor_id` and `organization_id` are
immutable — they cannot be sent, so they can never change.

Capacity is intentionally absent: it is derived from the room's `Bed` rows
(`COUNT(beds.id)`), never persisted or exposed.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RoomTypeEnum
from app.schemas.property import _strip


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_number: str | None = Field(default=None, min_length=1, max_length=50)
    room_type: RoomTypeEnum | None = None

    @field_validator("room_number")
    @classmethod
    def strip_room_number(cls, value: str | None) -> str | None:
        return _strip(value) if value else value