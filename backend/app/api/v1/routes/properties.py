"""Organization-scoped property CRUD endpoints.

Authorization is org-scoped through `PropertyService`: OWNER/MANAGER may write,
any member may read, and the platform-wide SUPER_ADMIN role bypasses.
Only `organization_id` is taken from the caller; the property's organization
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
from app.schemas.property import PropertyCreate, PropertyRead
from app.schemas.property_api import PropertyUpdate
from app.services.property_service import PropertyService

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("", response_model=PropertyRead, status_code=201)
def create_property(
    payload: PropertyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PropertyRead:
    try:
        property = PropertyService(db).create_property(current_user, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return PropertyRead.model_validate(property)


@router.get("", response_model=list[PropertyRead])
def list_properties(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PropertyRead]:
    try:
        properties = PropertyService(db).list_properties(current_user, organization_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    return [PropertyRead.model_validate(p) for p in properties]


@router.get("/{property_id}", response_model=PropertyRead)
def get_property(
    property_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PropertyRead:
    try:
        property = PropertyService(db).get_property(current_user, property_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return PropertyRead.model_validate(property)


@router.patch("/{property_id}", response_model=PropertyRead)
def update_property(
    property_id: UUID,
    payload: PropertyUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PropertyRead:
    try:
        property = PropertyService(db).update_property(current_user, property_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return PropertyRead.model_validate(property)