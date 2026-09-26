"""Data access for rooms. Repository layer only — no services, no endpoints.

Every read is scoped by `organization_id`: no unscoped read path exists.

Capacity is never read from `Room`; a room's size is the count of its `Bed`
rows (`COUNT(beds.id)`), computed when occupancy milestones need it.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.room import Room
from app.schemas.room import RoomCreate


class RoomRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, room_id: UUID) -> Room | None:
        return self._session.get(Room, room_id)

    def list_for_floor(self, floor_id: UUID) -> list[Room]:
        return list(
            self._session.scalars(
                select(Room)
                .where(Room.floor_id == floor_id)
                .order_by(Room.room_number)
            )
        )

    def exists_by_number(self, floor_id: UUID, room_number: str) -> bool:
        return self._session.scalar(
            select(Room.id)
            .where(
                Room.floor_id == floor_id,
                Room.room_number == room_number,
            )
            .limit(1)
        ) is not None

    def create(self, data: RoomCreate) -> Room:
        room = Room(**data.model_dump())
        self._session.add(room)
        self._session.commit()
        self._session.refresh(room)
        return room