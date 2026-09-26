"""Organization-scoped room CRUD endpoints.

Authorization is org-scoped through `RoomService`: OWNER/MANAGER may write,
any member may read, and the platform-wide SUPER_ADMIN role bypasses.
Only `organization_id` is taken from the caller; a room's organization and
floor always derive from the row itself.

Capacity is deliberately absent from the payload and response shapes — a
room's size is the count of its `Bed` rows, never stored or exposed.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.room import RoomCreate, RoomRead
from app.schemas.room_api import RoomUpdate
from app.services.room_service import RoomService

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=RoomRead, status_code=201)
def create_room(
    payload: RoomCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RoomRead:
    try:
        room = RoomService(db).create_room(current_user, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return RoomRead.model_validate(room)


@router.get("", response_model=list[RoomRead])
def list_rooms(
    organization_id: UUID,
    floor_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[RoomRead]:
    try:
        rooms = RoomService(db).list_rooms(current_user, organization_id, floor_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return [RoomRead.model_validate(r) for r in rooms]


@router.get("/{room_id}", response_model=RoomRead)
def get_room(
    room_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RoomRead:
    try:
        room = RoomService(db).get_room(current_user, room_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return RoomRead.model_validate(room)


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(
    room_id: UUID,
    payload: RoomUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RoomRead:
    try:
        room = RoomService(db).update_room(current_user, room_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return RoomRead.model_validate(room)