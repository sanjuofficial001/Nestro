"""Organization-scoped floor CRUD endpoints.

Authorization is org-scoped through `FloorService`: OWNER/MANAGER may write,
any member may read, and the platform-wide SUPER_ADMIN role bypasses.
Only `organization_id` is taken from the caller; a floor's organization and
building always derive from the row itself.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.floor import FloorCreate, FloorRead
from app.schemas.floor_api import FloorUpdate
from app.services.floor_service import FloorService

router = APIRouter(prefix="/floors", tags=["floors"])


@router.post("", response_model=FloorRead, status_code=201)
def create_floor(
    payload: FloorCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FloorRead:
    try:
        floor = FloorService(db).create_floor(current_user, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return FloorRead.model_validate(floor)


@router.get("", response_model=list[FloorRead])
def list_floors(
    organization_id: UUID,
    building_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FloorRead]:
    try:
        floors = FloorService(db).list_floors(
            current_user, organization_id, building_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return [FloorRead.model_validate(f) for f in floors]


@router.get("/{floor_id}", response_model=FloorRead)
def get_floor(
    floor_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FloorRead:
    try:
        floor = FloorService(db).get_floor(current_user, floor_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return FloorRead.model_validate(floor)


@router.patch("/{floor_id}", response_model=FloorRead)
def update_floor(
    floor_id: UUID,
    payload: FloorUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FloorRead:
    try:
        floor = FloorService(db).update_floor(current_user, floor_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return FloorRead.model_validate(floor)