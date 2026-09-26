"""Organization-scoped resident profile CRUD endpoints.

Authorization is org-scoped through `ResidentProfileService`: OWNER/MANAGER may
write, any member may read, and the platform-wide SUPER_ADMIN role bypasses.
Only `organization_id` is taken from the caller; a profile's organization and
membership always derive from the row itself.

Occupancy, bed assignment, and tenant stays are separate future milestones:
`property_id` is optional here and nothing on this surface tracks a stay.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.resident_profile import ResidentProfileCreate, ResidentProfileRead
from app.schemas.resident_profile_api import ResidentProfileUpdate
from app.services.resident_profile_service import ResidentProfileService

router = APIRouter(prefix="/resident-profiles", tags=["resident-profiles"])


@router.post("", response_model=ResidentProfileRead, status_code=201)
def create_resident_profile(
    payload: ResidentProfileCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResidentProfileRead:
    try:
        profile = ResidentProfileService(db).create_resident_profile(
            current_user, payload
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ResidentProfileRead.model_validate(profile)


@router.get("", response_model=list[ResidentProfileRead])
def list_resident_profiles(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ResidentProfileRead]:
    try:
        profiles = ResidentProfileService(db).list_resident_profiles(
            current_user, organization_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return [ResidentProfileRead.model_validate(p) for p in profiles]


@router.get("/{resident_profile_id}", response_model=ResidentProfileRead)
def get_resident_profile(
    resident_profile_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResidentProfileRead:
    try:
        profile = ResidentProfileService(db).get_resident_profile(
            current_user, resident_profile_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ResidentProfileRead.model_validate(profile)


@router.patch("/{resident_profile_id}", response_model=ResidentProfileRead)
def update_resident_profile(
    resident_profile_id: UUID,
    payload: ResidentProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ResidentProfileRead:
    try:
        profile = ResidentProfileService(db).update_resident_profile(
            current_user, resident_profile_id, payload
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return ResidentProfileRead.model_validate(profile)