"""Organization-scoped building CRUD endpoints.

Authorization is org-scoped through `BuildingService`: OWNER/MANAGER may write,
any member may read, and the platform-wide SUPER_ADMIN role bypasses.
Only `organization_id` is taken from the caller; a building's organization
always derives from the row itself.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.building import BuildingCreate, BuildingRead
from app.schemas.building_api import BuildingUpdate
from app.services.building_service import BuildingService

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.post("", response_model=BuildingRead, status_code=201)
def create_building(
    payload: BuildingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BuildingRead:
    try:
        building = BuildingService(db).create_building(current_user, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return BuildingRead.model_validate(building)


@router.get("", response_model=list[BuildingRead])
def list_buildings(
    organization_id: UUID,
    property_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[BuildingRead]:
    try:
        buildings = BuildingService(db).list_buildings(
            current_user, organization_id, property_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return [BuildingRead.model_validate(b) for b in buildings]


@router.get("/{building_id}", response_model=BuildingRead)
def get_building(
    building_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BuildingRead:
    try:
        building = BuildingService(db).get_building(current_user, building_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return BuildingRead.model_validate(building)


@router.patch("/{building_id}", response_model=BuildingRead)
def update_building(
    building_id: UUID,
    payload: BuildingUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BuildingRead:
    try:
        building = BuildingService(db).update_building(
            current_user, building_id, payload
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return BuildingRead.model_validate(building)