"""Organization-scoped bed CRUD endpoints.

Authorization is org-scoped through `BedService`: OWNER/MANAGER may write,
any member may read, and the platform-wide SUPER_ADMIN role bypasses.
Only `organization_id` is taken from the caller; a bed's organization and
room always derive from the row itself.

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
from app.schemas.bed import BedCreate, BedRead
from app.schemas.bed_api import BedUpdate
from app.services.bed_service import BedService

router = APIRouter(prefix="/beds", tags=["beds"])


@router.post("", response_model=BedRead, status_code=201)
def create_bed(
    payload: BedCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BedRead:
    try:
        bed = BedService(db).create_bed(current_user, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return BedRead.model_validate(bed)


@router.get("", response_model=list[BedRead])
def list_beds(
    organization_id: UUID,
    room_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[BedRead]:
    try:
        beds = BedService(db).list_beds(current_user, organization_id, room_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return [BedRead.model_validate(b) for b in beds]


@router.get("/{bed_id}", response_model=BedRead)
def get_bed(
    bed_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BedRead:
    try:
        bed = BedService(db).get_bed(current_user, bed_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return BedRead.model_validate(bed)


@router.patch("/{bed_id}", response_model=BedRead)
def update_bed(
    bed_id: UUID,
    payload: BedUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BedRead:
    try:
        bed = BedService(db).update_bed(current_user, bed_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return BedRead.model_validate(bed)